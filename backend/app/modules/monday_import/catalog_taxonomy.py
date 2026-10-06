"""Taxonomia de catálogos da migração Monday → Hub.

Cada valor de catálogo vindo da origem recebe uma das ações:

- EXISTING: já existe no Hub e é usado como está;
- CREATE: não existe e há evidência inequívoca e suficiente para criar
  (a origem da evidência fica registrada: MONDAY, EAP_TREE, LGE, MANUAL_MAPPING);
- CONFLICT: colide com um registro existente (identidade/nome divergente);
- UNRESOLVED: não há dados suficientes, ou as fontes divergem; o vínculo fica
  vazio e a pendência aparece no plan com o valor bruto preservado.

Só CONFLICT bloqueia o equipamento. UNRESOLVED é warning explícito: a migração
de uma obra não para por uma associação que pode ser resolvida depois.

Funções puras: recebem catálogos e evidências já carregados e não tocam no banco.
Nenhuma regra aqui depende de obra específica.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from app.domain.eap import AREA_CODE_RE, PROCESS_CODE_RE, EapLevel
from app.modules.monday_import.catalog_evidence import (
    EvidenceLookup,
    SupplierEvidence,
    evidence_key,
    reliable_label,
)
from app.modules.monday_import.normalization import canonical_text


class CatalogAction(StrEnum):
    EXISTING = "EXISTING"
    CREATE = "CREATE"
    CONFLICT = "CONFLICT"
    UNRESOLVED = "UNRESOLVED"


# Separação explícita. Um código fora destes dois conjuntos não bloqueia, como antes.
BLOCKING_ISSUE_CODES: frozenset[str] = frozenset(
    {
        "IMPORT_CONFLICT",
        "STAGE_CONFLICT",
        "UNKNOWN_STAGE_VALUE",
        "missing_current_stage",
        # Enquanto não houver representação aprovada para "Não se Aplica".
        "STAGE_NOT_APPLICABLE",
        "OPERATIONAL_STATUS_TRANSITION_UNSUPPORTED",
        "PARENT_IDENTITY_CONFLICT",
        "MONDAY_ITEM_ID_CONFLICT",
        # Valor obrigatório maior que a coluna: identidade nunca é truncada.
        "FIELD_TOO_LONG_REQUIRED",
        # Conflitos reais com registro existente no Hub.
        "EAP_CODE_LABEL_CONFLICT",
        "DISCIPLINE_CONFLICT",
        "WORK_PACKAGE_CONFLICT",
        "SUPPLIER_CONFLICT",
    }
)

NON_BLOCKING_ISSUE_CODES: frozenset[str] = frozenset(
    {
        "RESPONSIBLE_UNRESOLVED",
        "DISCIPLINE_CODE_REQUIRED",
        "DISCIPLINE_COMPOSITE_UNRESOLVED",
        "EAP_LABEL_VARIANT",
        # Campo opcional maior que a coluna: não gravado, valor bruto no staging.
        "FIELD_TOO_LONG",
        "WORK_PACKAGE_UNRESOLVED",
        "MULTIPLE_EAP_CANDIDATES",
        "NO_EAP",
        "EAP_NAME_REQUIRED",
        "EAP_PARENT_REQUIRED",
        "EAP_NOT_FOUND",
        "SUPPLIER_UNRESOLVED",
        "SUPPLIER_MULTIPLE_CANDIDATES",
        # Fontes de evidência divergentes: nada é criado, nada é escolhido.
        "CATALOG_EVIDENCE_CONFLICT",
    }
)


def is_blocking_issue(code: str) -> bool:
    return code in BLOCKING_ISSUE_CODES


def _evidence_conflict_detail(lookup: EvidenceLookup) -> dict[str, str]:
    return {f"{item.source.value}#{index}": item.value for index, item in enumerate(lookup.conflict)}


# --- EAP ---------------------------------------------------------------------


@dataclass(slots=True, frozen=True)
class EapCatalogEntry:
    """Nó de EAP existente no Hub. Inclui inativos: sem isso um código inativo
    pareceria "novo" e violaria a unicidade de `eap_node.code`."""

    id: str
    code: str
    name: str
    level: str
    active: bool


@dataclass(slots=True, frozen=True)
class EapNodeSpec:
    code: str
    name: str
    level: EapLevel
    parent_code: str | None = None
    evidence_source: str | None = None


@dataclass(slots=True, frozen=True)
class EapDecision:
    action: CatalogAction
    code: str | None = None
    node_id: str | None = None
    # Nós a criar, na ordem de dependência (PROCESS antes de AREA). Só em CREATE.
    creates: tuple[EapNodeSpec, ...] = ()
    issue_code: str | None = None
    message: str | None = None
    detail: dict[str, str] = field(default_factory=dict)


EapNameEvidence = Callable[[str], EvidenceLookup]

reliable_eap_label = reliable_label


def eap_level_for_code(code: str) -> EapLevel | None:
    if PROCESS_CODE_RE.match(code):
        return EapLevel.PROCESS
    if AREA_CODE_RE.match(code):
        return EapLevel.AREA
    return None


def _no_evidence(_: str) -> EvidenceLookup:
    return EvidenceLookup()


def codes_by_eap_name(catalog: Mapping[str, EapCatalogEntry]) -> dict[str, set[str]]:
    """Nome oficial comparável → códigos ativos que o usam."""
    index: dict[str, set[str]] = {}
    for entry in catalog.values():
        if entry.active:
            index.setdefault(evidence_key(entry.name), set()).add(entry.code)
    return index


def decide_eap(
    codes: tuple[str, ...],
    label: str | None,
    catalog: Mapping[str, EapCatalogEntry],
    name_evidence: EapNameEvidence | None = None,
    codes_by_name: Mapping[str, set[str]] | None = None,
) -> EapDecision:
    """Decide a EAP de uma localização já reduzida a códigos canônicos.

    `label` é o rótulo que acompanha o código na célula (ex.: "23.C - Nome").
    `name_evidence(code)` consulta nomes comprovados (catálogo oficial, Monday,
    LGE, mapping manual) e só é usada para códigos que NÃO existem no Hub.

    Código existente: rótulo igual ao nome oficial → EXISTING; rótulo que é o nome
    oficial de OUTRO código → CONFLICT (EAP_CODE_LABEL_CONFLICT); qualquer outra
    variante (abreviação, nome curto) → EXISTING com EAP_LABEL_VARIANT.
    `codes_by_name` (nome comparável → códigos) evita recalcular o índice.
    """
    lookup = name_evidence or _no_evidence
    if not codes:
        return EapDecision(
            CatalogAction.UNRESOLVED,
            issue_code="NO_EAP",
            message="Localização sem código EAP; o equipamento fica sem EAP até um mapeamento.",
        )
    if len(codes) > 1:
        return EapDecision(
            CatalogAction.UNRESOLVED,
            issue_code="MULTIPLE_EAP_CANDIDATES",
            message="Localização cita mais de uma EAP; nenhuma é escolhida automaticamente.",
            detail={"candidates": ", ".join(codes)},
        )

    code = codes[0]
    level = eap_level_for_code(code)
    if level is None:
        return EapDecision(
            CatalogAction.UNRESOLVED,
            code=code,
            issue_code="EAP_NOT_FOUND",
            message="Código EAP fora do formato reconhecido pelo Hub.",
        )

    label_clean = reliable_eap_label(label)
    existing = catalog.get(code)
    if existing is not None:
        if not existing.active:
            return EapDecision(
                CatalogAction.UNRESOLVED,
                code=code,
                issue_code="EAP_NOT_FOUND",
                message="Código EAP existe no Hub, mas está inativo.",
            )
        # O código é a identidade; o nome oficial é a descrição canônica.
        if not label_clean or evidence_key(label_clean) == evidence_key(existing.name):
            return EapDecision(CatalogAction.EXISTING, code=code, node_id=existing.id)
        other_codes = sorted(
            other
            for other in (codes_by_name or codes_by_eap_name(catalog)).get(evidence_key(label_clean), ())
            if other != code
        )
        if other_codes:
            # O rótulo é exatamente o nome oficial de OUTRO código: não é abreviação.
            return EapDecision(
                CatalogAction.CONFLICT,
                code=code,
                node_id=existing.id,
                issue_code="EAP_CODE_LABEL_CONFLICT",
                message="O rótulo da origem é o nome oficial de outro código EAP. Revise o código na origem.",
                detail={
                    "hubName": existing.name,
                    "sourceName": label_clean,
                    "labelMatchesCodes": ", ".join(other_codes),
                },
            )
        # Abreviação ou variante do nome: vale o código + nome oficiais, com aviso.
        return EapDecision(
            CatalogAction.EXISTING,
            code=code,
            node_id=existing.id,
            issue_code="EAP_LABEL_VARIANT",
            message="Rótulo da origem difere do nome oficial; usado o código e o nome oficiais.",
            detail={"hubName": existing.name, "sourceName": label_clean},
        )

    own = lookup(code)
    if own.conflict:
        return EapDecision(
            CatalogAction.UNRESOLVED,
            code=code,
            issue_code="CATALOG_EVIDENCE_CONFLICT",
            message="Fontes divergem quanto ao nome desta EAP nova; nada é criado.",
            detail=_evidence_conflict_detail(own),
        )
    if not own.found or own.value is None:
        return EapDecision(
            CatalogAction.UNRESOLVED,
            code=code,
            issue_code="EAP_NAME_REQUIRED",
            message="EAP nova sem nome confiável em nenhuma fonte; não é criada.",
        )
    own_spec_source = own.source.value if own.source else None

    if level is EapLevel.PROCESS:
        spec = EapNodeSpec(code=code, name=own.value, level=level, evidence_source=own_spec_source)
        return EapDecision(CatalogAction.CREATE, code=code, creates=(spec,))

    area_spec = EapNodeSpec(
        code=code,
        name=own.value,
        level=level,
        parent_code=code.split(".", 1)[0],
        evidence_source=own_spec_source,
    )
    parent_code = area_spec.parent_code or ""
    parent = catalog.get(parent_code)
    if parent is not None:
        if not parent.active:
            return EapDecision(
                CatalogAction.UNRESOLVED,
                code=code,
                issue_code="EAP_PARENT_REQUIRED",
                message=f"Processo pai {parent_code} existe, mas está inativo.",
            )
        return EapDecision(CatalogAction.CREATE, code=code, creates=(area_spec,))

    parent_lookup = lookup(parent_code)
    if parent_lookup.conflict:
        return EapDecision(
            CatalogAction.UNRESOLVED,
            code=code,
            issue_code="CATALOG_EVIDENCE_CONFLICT",
            message=f"Fontes divergem quanto ao nome do processo pai {parent_code}; nada é criado.",
            detail=_evidence_conflict_detail(parent_lookup),
        )
    if not parent_lookup.found or parent_lookup.value is None:
        return EapDecision(
            CatalogAction.UNRESOLVED,
            code=code,
            issue_code="EAP_PARENT_REQUIRED",
            message=f"Processo pai {parent_code} não existe no Hub e não há nome confiável para criá-lo.",
        )
    parent_spec = EapNodeSpec(
        code=parent_code,
        name=parent_lookup.value,
        level=EapLevel.PROCESS,
        evidence_source=parent_lookup.source.value if parent_lookup.source else None,
    )
    return EapDecision(CatalogAction.CREATE, code=code, creates=(parent_spec, area_spec))


def decide_project_eap(eap_node_id: str, linked_node_ids: set[str]) -> CatalogAction:
    """ProjectEap é único por (contexto, nó): existe → EXISTING; senão → CREATE."""
    return CatalogAction.EXISTING if eap_node_id in linked_node_ids else CatalogAction.CREATE


# --- Discipline --------------------------------------------------------------


@dataclass(slots=True, frozen=True)
class DisciplineEntry:
    id: str
    code: str
    name: str
    active: bool


@dataclass(slots=True, frozen=True)
class DisciplineDecision:
    action: CatalogAction
    name: str | None = None
    code: str | None = None
    discipline_id: str | None = None
    evidence_source: str | None = None
    issue_code: str | None = None
    message: str | None = None
    detail: dict[str, str] = field(default_factory=dict)


# Aliases EXPLÍCITOS e aprovados (Gate 2) de valores da origem para o nome oficial
# da disciplina. Não é fuzzy: só a forma comparável exata da chave é aceita.
DISCIPLINE_ALIASES: Mapping[str, str] = {
    "Metal Mec.": "Metal Mecânica.",
}
_DISCIPLINE_ALIAS_INDEX = {evidence_key(source): target for source, target in DISCIPLINE_ALIASES.items()}
_COMPOSITE_RE = re.compile(r"[&/+]")


def discipline_target_name(name: str | None) -> str | None:
    """Nome oficial para um valor da origem: o alias explícito, ou o próprio valor."""
    if name is None or not name.strip():
        return None
    return _DISCIPLINE_ALIAS_INDEX.get(evidence_key(name), name.strip())


def is_composite_discipline(name: str) -> bool:
    """ "E&I", "Civil/Grãos": mais de uma disciplina/contexto num valor só."""
    return bool(_COMPOSITE_RE.search(name))


def decide_discipline(
    name: str | None,
    code_evidence: EvidenceLookup,
    by_name: Mapping[str, DisciplineEntry],
    by_code: Mapping[str, DisciplineEntry],
) -> DisciplineDecision | None:
    """`code_evidence` é a sigla comprovada por alguma fonte. Nunca é gerada aqui.
    Sem nome na origem não há decisão."""
    if name is None or not name.strip():
        return None
    name_clean = name.strip()
    if is_composite_discipline(name_clean) and not code_evidence.found:
        # Valor composto ("E&I", "Civil/Grãos") nunca é resolvido por nome, nem para
        # um registro legado de mesmo nome: só mapping explícito ou fonte oficial.
        return DisciplineDecision(
            CatalogAction.UNRESOLVED,
            name=name_clean,
            issue_code="DISCIPLINE_COMPOSITE_UNRESOLVED",
            message="Valor combina mais de uma disciplina/contexto; o equipamento admite uma só. "
            "Nenhuma é escolhida.",
            detail={"sourceValue": name_clean},
        )
    entry = by_name.get(canonical_text(name_clean))

    if entry is not None:
        if not entry.active:
            return DisciplineDecision(
                CatalogAction.UNRESOLVED,
                name=name_clean,
                issue_code="DISCIPLINE_CODE_REQUIRED",
                message="Disciplina existe no Hub, mas está inativa.",
            )
        proven = code_evidence.value
        if proven and canonical_text(proven) != canonical_text(entry.code):
            return DisciplineDecision(
                CatalogAction.CONFLICT,
                name=name_clean,
                code=proven,
                discipline_id=entry.id,
                evidence_source=code_evidence.source.value if code_evidence.source else None,
                issue_code="DISCIPLINE_CONFLICT",
                message="Disciplina com mesmo nome e sigla diferente no Hub. Não sobrescrita.",
                detail={"hubCode": entry.code, "sourceCode": proven},
            )
        return DisciplineDecision(
            CatalogAction.EXISTING, name=name_clean, code=entry.code, discipline_id=entry.id
        )

    if code_evidence.conflict:
        return DisciplineDecision(
            CatalogAction.UNRESOLVED,
            name=name_clean,
            issue_code="CATALOG_EVIDENCE_CONFLICT",
            message="Fontes divergem quanto à sigla desta disciplina; nada é criado.",
            detail=_evidence_conflict_detail(code_evidence),
        )
    if not code_evidence.found or code_evidence.value is None:
        return DisciplineDecision(
            CatalogAction.UNRESOLVED,
            name=name_clean,
            issue_code="DISCIPLINE_CODE_REQUIRED",
            message="Disciplina sem sigla comprovada; não é criada e não recebe código inventado.",
        )

    code = code_evidence.value.strip()
    other = by_code.get(canonical_text(code))
    if other is not None:
        return DisciplineDecision(
            CatalogAction.CONFLICT,
            name=name_clean,
            code=code,
            discipline_id=other.id,
            evidence_source=code_evidence.source.value if code_evidence.source else None,
            issue_code="DISCIPLINE_CONFLICT",
            message="Sigla comprovada já usada por outra disciplina no Hub. Não sobrescrita.",
            detail={"hubName": other.name, "sourceName": name_clean},
        )
    return DisciplineDecision(
        CatalogAction.CREATE,
        name=name_clean,
        code=code,
        evidence_source=code_evidence.source.value if code_evidence.source else None,
    )


# --- WorkPackage -------------------------------------------------------------


@dataclass(slots=True, frozen=True)
class WorkPackageEntry:
    id: str
    code: str
    name: str
    active: bool


@dataclass(slots=True, frozen=True)
class WorkPackageDecision:
    action: CatalogAction
    code: str
    name: str | None = None
    work_package_id: str | None = None
    evidence_source: str | None = None
    issue_code: str | None = None
    message: str | None = None
    detail: dict[str, str] = field(default_factory=dict)


def decide_work_package(
    code: str,
    name_evidence: EvidenceLookup,
    by_code: Mapping[str, WorkPackageEntry],
) -> WorkPackageDecision:
    """`by_code` contém só os WPs do ProjectContext atual (WP de outro contexto nunca
    é reutilizado). Um código informado explicitamente pelo Monday é suficiente para
    a criação controlada; enquanto não houver nome separado, o próprio código é o
    rótulo provisório e auditável do catálogo."""
    code_clean = code.strip()
    entry = by_code.get(canonical_text(code_clean))

    if entry is not None:
        if not entry.active:
            return WorkPackageDecision(
                CatalogAction.UNRESOLVED,
                code=code_clean,
                issue_code="WORK_PACKAGE_UNRESOLVED",
                message="Work Package existe neste contexto, mas está inativo.",
            )
        proven = name_evidence.value
        if proven and canonical_text(proven) != canonical_text(entry.name):
            return WorkPackageDecision(
                CatalogAction.CONFLICT,
                code=code_clean,
                name=proven,
                work_package_id=entry.id,
                issue_code="WORK_PACKAGE_CONFLICT",
                message="Work Package com o mesmo código e nome diferente neste contexto. Não sobrescrito.",
                detail={"hubName": entry.name, "sourceName": proven},
            )
        return WorkPackageDecision(CatalogAction.EXISTING, code=code_clean, work_package_id=entry.id)

    if name_evidence.conflict:
        return WorkPackageDecision(
            CatalogAction.UNRESOLVED,
            code=code_clean,
            issue_code="CATALOG_EVIDENCE_CONFLICT",
            message="Fontes divergem quanto ao nome deste Work Package; nada é criado.",
            detail=_evidence_conflict_detail(name_evidence),
        )
    if not name_evidence.found or name_evidence.value is None:
        return WorkPackageDecision(CatalogAction.CREATE, code=code_clean, name=code_clean)
    return WorkPackageDecision(
        CatalogAction.CREATE,
        code=code_clean,
        name=name_evidence.value,
        evidence_source=name_evidence.source.value if name_evidence.source else None,
    )


# --- Supplier ----------------------------------------------------------------


@dataclass(slots=True, frozen=True)
class SupplierEntry:
    id: str
    corporate_code: str | None
    legal_name: str
    trade_name: str | None
    active: bool


@dataclass(slots=True, frozen=True)
class SupplierIndex:
    by_code: Mapping[str, SupplierEntry]
    by_alias: Mapping[str, SupplierEntry]  # alias canônico → fornecedor (ambíguos excluídos)
    by_name: Mapping[str, SupplierEntry]  # razão/fantasia canônica → fornecedor (ambíguos excluídos)


@dataclass(slots=True, frozen=True)
class SupplierDecision:
    action: CatalogAction
    key: str
    supplier_id: str | None = None
    payload: dict[str, str] = field(default_factory=dict)
    evidence_source: str | None = None
    issue_code: str | None = None
    message: str | None = None
    detail: dict[str, str] = field(default_factory=dict)


_MULTI_CODE_RE = re.compile(r"[/;,|]|\s+e\s+")
_CORPORATE_CODE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def split_supplier_codes(raw_code: str | None) -> list[str]:
    if raw_code is None or not str(raw_code).strip():
        return []
    return [part.strip() for part in _MULTI_CODE_RE.split(str(raw_code)) if part and part.strip()]


def decide_supplier(
    raw_code: str | None,
    raw_names: list[str],
    index: SupplierIndex,
    manual: Callable[[str], SupplierEvidence | None],
) -> SupplierDecision | None:
    """Ordem: código corporativo exato → SupplierAlias → nome exato normalizado →
    evidência (manual) para criar → UNRESOLVED. Sem fuzzy. Sem dado, sem decisão."""
    codes = split_supplier_codes(raw_code)
    names = [name.strip() for name in raw_names if name and name.strip()]
    if not codes and not names:
        return None
    if len(codes) > 1 or len(names) > 1:
        return SupplierDecision(
            CatalogAction.UNRESOLVED,
            key=raw_code or "; ".join(names),
            issue_code="SUPPLIER_MULTIPLE_CANDIDATES",
            message="Origem cita mais de um fornecedor; o modelo atual admite um. Nenhum é escolhido.",
            detail={"sourceValue": raw_code or "; ".join(names)},
        )

    code = codes[0] if codes else None
    name = names[0] if names else None
    by_code = index.by_code.get(code) if code else None
    by_name = None
    if name:
        by_name = index.by_alias.get(canonical_text(name)) or index.by_name.get(canonical_text(name))

    if by_code is not None and by_name is not None and by_code.id != by_name.id:
        return SupplierDecision(
            CatalogAction.CONFLICT,
            key=code or name or "",
            issue_code="SUPPLIER_CONFLICT",
            message="Código e nome da origem apontam para fornecedores diferentes no Hub.",
            detail={"byCode": by_code.legal_name, "byName": by_name.legal_name},
        )
    found = by_code or by_name
    if found is not None:
        if not found.active:
            return SupplierDecision(
                CatalogAction.UNRESOLVED,
                key=code or name or "",
                issue_code="SUPPLIER_UNRESOLVED",
                message="Fornecedor encontrado está inativo no Hub; vínculo não criado.",
            )
        return SupplierDecision(CatalogAction.EXISTING, key=code or name or "", supplier_id=found.id)

    if code is not None and _CORPORATE_CODE_RE.match(code):
        evidence = manual(code)
        if evidence is not None:
            payload = {"corporate_code": code, "legal_name": evidence.legal_name}
            if evidence.trade_name:
                payload["trade_name"] = evidence.trade_name
            if evidence.tax_id:
                payload["tax_id"] = evidence.tax_id
            return SupplierDecision(
                CatalogAction.CREATE, key=code, payload=payload, evidence_source=evidence.source.value
            )
    return SupplierDecision(
        CatalogAction.UNRESOLVED,
        key=code or name or "",
        issue_code="SUPPLIER_UNRESOLVED",
        message="Fornecedor não encontrado no Hub e sem dados suficientes (razão social) para criar.",
        detail={"sourceValue": code or name or ""},
    )
