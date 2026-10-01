"""Consolidação da carga de fornecedores oficiais do LEM F2 — sem banco.

Regras (nenhuma usa similaridade de nome):

- só aliases com "Classificação validada = CONFIRMADO" viram fornecedor;
- o fornecedor é consolidado por `corporate_code`: vários aliases do Monday
  com o mesmo código viram UM fornecedor e N aliases;
- o vínculo equipamento → fornecedor só é proposto quando o item está
  CONFIRMADO, tem código, e o próprio nome Monday do item é um alias
  CONFIRMADO com esse mesmo código;
- PROVÁVEL, AMBÍGUO, NÃO ENCONTRADO, SEM FORNECEDOR e o marcador
  "EM DEFINIÇÃO" nunca geram fornecedor nem vínculo — aparecem no relatório;
- se as contagens essenciais da planilha divergirem do esperado, a carga é
  abortada (`SupplierReconciliationError`), nunca segue silenciosamente.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from typing import Any

from app.modules.monday_import.mappings import provisional_equipment_key
from app.modules.monday_import.normalization import NormalizationError, canonical_text, normalize_boolean
from app.modules.supplier_import.workbook import AliasRow, EquipmentRow, SupplierWorkbook

CONFIRMED = "CONFIRMADO"
PROBABLE = "PROVÁVEL"
AMBIGUOUS = "AMBÍGUO"
NOT_FOUND = "NÃO ENCONTRADO"
NO_SUPPLIER = "SEM FORNECEDOR"
PLACEHOLDER_NAMES = frozenset({"em definicao"})

ALIAS_SOURCE = "MONDAY"
_CODE_RE = re.compile(r"^\d{1,20}$")
_TAX_ID_RE = re.compile(r"^(\d{11}|\d{14})$")


@dataclass(slots=True, frozen=True)
class ExpectedCounts:
    equipments: int
    with_supplier_text: int
    with_corporate_code: int
    confirmed_aliases: int
    confirmed_codes: int
    probable: int
    ambiguous: int
    not_found: int


# Números da auditoria validada de 2026-09-29 (Monday x base corporativa).
LEM_F2_EXPECTED = ExpectedCounts(
    equipments=99,
    with_supplier_text=98,
    with_corporate_code=96,
    confirmed_aliases=72,
    confirmed_codes=64,
    probable=1,
    ambiguous=15,
    not_found=1,
)


@dataclass(slots=True)
class SupplierCandidate:
    corporate_code: str
    legal_name: str
    tax_id: str | None
    active: bool
    aliases: list[str] = field(default_factory=list)


@dataclass(slots=True, frozen=True)
class AliasCandidate:
    alias: str
    corporate_code: str
    source: str
    context: str


@dataclass(slots=True, frozen=True)
class LinkCandidate:
    equipment_name: str
    equipment_source_key: str
    corporate_code: str
    supplier_alias: str
    sheet_row: int


@dataclass(slots=True, frozen=True)
class BlockedRecord:
    level: str  # "alias" (nome Monday) ou "equipment" (item do board)
    name: str | None
    classification: str | None
    reason: str
    corporate_code: str | None = None
    equipment_name: str | None = None
    sheet_row: int | None = None


@dataclass(slots=True, frozen=True)
class CountCheck:
    name: str
    expected: int
    actual: int

    @property
    def ok(self) -> bool:
        return self.expected == self.actual


@dataclass(slots=True)
class SupplierImportPlan:
    source_file: str
    file_sha256: str
    alias_context: str
    checks: list[CountCheck] = field(default_factory=list)
    suppliers: dict[str, SupplierCandidate] = field(default_factory=dict)
    aliases: list[AliasCandidate] = field(default_factory=list)
    links: list[LinkCandidate] = field(default_factory=list)
    blocked: list[BlockedRecord] = field(default_factory=list)
    invalid_codes: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def checks_ok(self) -> bool:
        return all(check.ok for check in self.checks)

    def blocked_by(self, classification: str) -> list[BlockedRecord]:
        return [item for item in self.blocked if item.classification == classification]

    def to_dict(self) -> dict[str, Any]:
        return {
            "sourceFile": self.source_file,
            "fileSha256": self.file_sha256,
            "aliasContext": self.alias_context,
            "checks": [{**asdict(check), "ok": check.ok} for check in self.checks],
            "suppliers": [asdict(item) for item in self.suppliers.values()],
            "aliases": [asdict(item) for item in self.aliases],
            "links": [asdict(item) for item in self.links],
            "blocked": [asdict(item) for item in self.blocked],
            "invalidCodes": self.invalid_codes,
            "errors": self.errors,
        }


class SupplierReconciliationError(RuntimeError):
    """As contagens essenciais da planilha não batem com o esperado."""

    def __init__(self, plan: SupplierImportPlan) -> None:
        self.plan = plan
        mismatches = [
            f"{c.name}: esperado={c.expected}, planilha={c.actual}" for c in plan.checks if not c.ok
        ]
        super().__init__("Carga abortada — reconciliação divergente: " + "; ".join(mismatches))


def _is_placeholder(name: str | None) -> bool:
    return canonical_text(name) in PLACEHOLDER_NAMES


def _count_checks(workbook: SupplierWorkbook, expected: ExpectedCounts) -> list[CountCheck]:
    confirmed = [row for row in workbook.confirmed if row.classification == CONFIRMED]
    return [
        CountCheck("equipamentos F2", expected.equipments, len(workbook.equipments)),
        CountCheck(
            "equipamentos com fornecedor textual",
            expected.with_supplier_text,
            sum(1 for row in workbook.equipments if row.supplier_text),
        ),
        CountCheck(
            "equipamentos com Cód. Fornecedor. CS",
            expected.with_corporate_code,
            sum(1 for row in workbook.equipments if row.corporate_code),
        ),
        CountCheck("aliases CONFIRMADOS", expected.confirmed_aliases, len(confirmed)),
        CountCheck(
            "códigos corporativos CONFIRMADOS distintos",
            expected.confirmed_codes,
            len({row.corporate_code for row in confirmed if row.corporate_code}),
        ),
        CountCheck("aliases PROVÁVEIS", expected.probable, len(workbook.probable)),
        CountCheck("aliases AMBÍGUOS", expected.ambiguous, len(workbook.ambiguous)),
        CountCheck("aliases NÃO ENCONTRADOS / marcador", expected.not_found, len(workbook.not_found)),
    ]


def _tax_id(row: AliasRow, errors: list[str]) -> str | None:
    if row.tax_id is None:  # vazio ou "N/A" (fornecedor estrangeiro)
        return None
    digits = re.sub(r"\D", "", row.tax_id)
    if not _TAX_ID_RE.fullmatch(digits):
        errors.append(f"Confirmados linha {row.row_number}: documento inválido {row.tax_id!r} ({row.alias})")
        return None
    return digits


def _active(row: AliasRow, errors: list[str]) -> bool:
    try:
        value = normalize_boolean(row.active, empty=None)
    except NormalizationError:
        value = None
    if value is None:
        errors.append(f"Confirmados linha {row.row_number}: 'Ativo' inválido {row.active!r} ({row.alias})")
        return False
    return value


def _consolidate_suppliers(plan: SupplierImportPlan, workbook: SupplierWorkbook) -> dict[str, str]:
    """Devolve alias → corporate_code dos aliases CONFIRMADOS aceitos."""
    alias_codes: dict[str, str] = {}
    for row in workbook.confirmed:
        if row.classification != CONFIRMED:
            plan.blocked.append(
                BlockedRecord("alias", row.alias, row.classification, "fora da aba de confirmados válidos")
            )
            continue
        if row.alias is None or _is_placeholder(row.alias):
            plan.errors.append(
                f"Confirmados linha {row.row_number}: nome {row.alias!r} é marcador/vazio "
                "e não vira fornecedor"
            )
            continue
        code = row.corporate_code
        if code is None or not _CODE_RE.fullmatch(code):
            plan.invalid_codes.append(
                {"sheet": row.sheet, "row": row.row_number, "alias": row.alias, "code": code}
            )
            plan.errors.append(f"Confirmados linha {row.row_number}: código corporativo inválido {code!r}")
            continue
        if row.legal_name is None:
            plan.errors.append(
                f"Confirmados linha {row.row_number}: razão social oficial vazia ({row.alias})"
            )
            continue
        tax_id = _tax_id(row, plan.errors)
        active = _active(row, plan.errors)

        existing_code = alias_codes.get(row.alias)
        if existing_code is not None and existing_code != code:
            plan.errors.append(
                f"Alias {row.alias!r} aponta para códigos diferentes: {existing_code} e {code}"
            )
            continue
        alias_codes[row.alias] = code

        candidate = plan.suppliers.get(code)
        if candidate is None:
            plan.suppliers[code] = SupplierCandidate(code, row.legal_name, tax_id, active, [row.alias])
        else:
            if (candidate.legal_name, candidate.tax_id, candidate.active) != (row.legal_name, tax_id, active):
                plan.errors.append(
                    f"Código {code}: dados oficiais divergentes entre aliases "
                    f"({candidate.aliases[0]!r} x {row.alias!r})"
                )
            if row.alias not in candidate.aliases:
                candidate.aliases.append(row.alias)
        plan.aliases.append(AliasCandidate(row.alias, code, ALIAS_SOURCE, plan.alias_context))

    by_tax_id: dict[str, set[str]] = defaultdict(set)
    for candidate in plan.suppliers.values():
        if candidate.tax_id is not None:
            by_tax_id[candidate.tax_id].add(candidate.corporate_code)
    for tax_id, codes in by_tax_id.items():
        if len(codes) > 1:
            plan.errors.append(f"Documento {tax_id} aparece em códigos diferentes: {sorted(codes)}")
    return alias_codes


def _blocked_alias_rows(plan: SupplierImportPlan, workbook: SupplierWorkbook) -> None:
    for rows, classification in (
        (workbook.probable, PROBABLE),
        (workbook.ambiguous, AMBIGUOUS),
        (workbook.not_found, NOT_FOUND),
    ):
        for row in rows:
            reason = (
                "marcador de pendência, não é empresa"
                if _is_placeholder(row.alias)
                else (f"classificação {classification}: exige revisão humana")
            )
            plan.blocked.append(
                BlockedRecord(
                    "alias", row.alias, classification, reason, row.corporate_code, sheet_row=row.row_number
                )
            )


def _plan_links(plan: SupplierImportPlan, workbook: SupplierWorkbook, alias_codes: dict[str, str]) -> None:
    alias_classification = {
        row.alias: classification
        for rows, classification in (
            (workbook.probable, PROBABLE),
            (workbook.ambiguous, AMBIGUOUS),
            (workbook.not_found, NOT_FOUND),
        )
        for row in rows
    }
    seen_keys: dict[str, int] = {}
    for row in workbook.equipments:
        if row.equipment is None:
            plan.errors.append(f"Fornecedores F2 linha {row.row_number}: equipamento sem nome")
            continue
        key = provisional_equipment_key(row.equipment)
        if key in seen_keys:
            plan.errors.append(
                f"Fornecedores F2 linhas {seen_keys[key]} e {row.row_number}: "
                f"equipamento repetido {row.equipment!r}"
            )
            continue
        seen_keys[key] = row.row_number

        if row.corporate_code is not None and not _CODE_RE.fullmatch(row.corporate_code):
            plan.invalid_codes.append(
                {
                    "sheet": "Fornecedores F2",
                    "row": row.row_number,
                    "equipment": row.equipment,
                    "code": row.corporate_code,
                }
            )
        blocked = _equipment_block_reason(row, alias_codes, alias_classification)
        if blocked is not None:
            reason, classification = blocked
            plan.blocked.append(
                BlockedRecord(
                    "equipment",
                    row.supplier_text,
                    classification,
                    reason,
                    row.corporate_code,
                    equipment_name=row.equipment,
                    sheet_row=row.row_number,
                )
            )
            continue
        assert row.corporate_code is not None and row.supplier_text is not None
        plan.links.append(
            LinkCandidate(row.equipment, key, row.corporate_code, row.supplier_text, row.row_number)
        )


def _equipment_block_reason(
    row: EquipmentRow, alias_codes: dict[str, str], alias_classification: dict[str | None, str]
) -> tuple[str, str | None] | None:
    """(motivo, classificação reportada) quando o item NÃO pode ser vinculado; None se pode."""
    if row.corporate_code is not None and not _CODE_RE.fullmatch(row.corporate_code):
        return "código corporativo inválido", row.classification
    if _is_placeholder(row.supplier_text):
        return "marcador 'EM DEFINIÇÃO' não é fornecedor", NOT_FOUND
    if row.classification != CONFIRMED:
        return f"classificação do item {row.classification}: não vincula automaticamente", row.classification
    if row.supplier_text is None or row.corporate_code is None:
        return "item CONFIRMADO sem fornecedor textual ou sem código", row.classification
    confirmed_code = alias_codes.get(row.supplier_text)
    if confirmed_code is None:
        name_classification = alias_classification.get(row.supplier_text)
        suffix = f" (classificação do nome: {name_classification})" if name_classification else ""
        return (
            f"fornecedor {row.supplier_text!r} não é alias CONFIRMADO{suffix}",
            name_classification or row.classification,
        )
    if confirmed_code != row.corporate_code:
        return (
            f"código do item ({row.corporate_code}) diverge do alias confirmado ({confirmed_code})",
            row.classification,
        )
    return None


def build_supplier_import_plan(
    workbook: SupplierWorkbook,
    *,
    alias_context: str,
    expected: ExpectedCounts | None = LEM_F2_EXPECTED,
) -> SupplierImportPlan:
    """Monta o plano puro. `expected=None` desliga os checks de contagem
    (usado só em testes com planilhas mínimas)."""
    plan = SupplierImportPlan(workbook.source_file, workbook.file_sha256, alias_context)
    if expected is not None:
        plan.checks = _count_checks(workbook, expected)
        if not plan.checks_ok:
            raise SupplierReconciliationError(plan)
    alias_codes = _consolidate_suppliers(plan, workbook)
    _blocked_alias_rows(plan, workbook)
    _plan_links(plan, workbook, alias_codes)
    return plan
