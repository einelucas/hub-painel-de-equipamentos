"""Reconciliação READ-ONLY de um valor de Área/EAP com o catálogo EAP oficial — pura, sem I/O.

Entrada: o MESMO valor que o importador Monday entende como área
(`normalized["area_name"]`) e o catálogo versionado (`app/data/eap_catalog.json`).
Saída: uma classificação explícita. Nada aqui grava vínculo; um MATCH é só
candidato a vínculo futuro.

Regras (ordem = precedência):
1. Mais de uma EAP estruturada distinta no mesmo valor → REVIEW_MULTIPLE_EAP.
2. Valor com código (`parse_eap_reference`): o código decide; o nome só valida.
   - código em `review_required` do catálogo → REVIEW_EAP_CATALOG;
   - código fora do catálogo → UNRESOLVED_UNKNOWN_CODE;
   - nome divergente do oficial → REVIEW_NAME_MISMATCH;
   - nome igual → MATCH_CODE_AND_NAME; sem nome → MATCH_CODE.
3. Valor sem código listado em `non_linkable_values` (decisão aprovada, ex.: "Geral")
   → UNRESOLVED_GENERIC_VALUE, antes de qualquer comparação de nome.
4. Valor sem código: igualdade EXATA do nome normalizado (`comparable_eap_name`:
   acentos, caixa, espaços) — sem fuzzy, sem inferir pelo nome do equipamento.
   - 1 candidato PROCESS/AREA carregável → MATCH_UNIQUE_NAME;
   - 1 candidato em `review_required` → REVIEW_EAP_CATALOG;
   - 2+ candidatos → UNRESOLVED_AMBIGUOUS_NAME;
   - nenhum nome oficial igual, mas alias APROVADO e versionado
     (`app/data/eap_aliases.json`, igualdade exata) → MATCH_APPROVED_ALIAS;
   - nenhum (ou só ilha, que não é elegível) → UNRESOLVED_GENERIC_VALUE.

Prefixo: o esperado do projeto é desconhecido, então nunca há
EAP_PREFIX_MISMATCH — o prefixo encontrado é só registrado como evidência
(`observed_prefix`), separado do código corporativo.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from app.domain.eap import (
    EapIssueCode,
    EapLevel,
    check_against_catalog,
    comparable_eap_name,
    parse_eap_reference,
)
from app.modules.eap_catalog.catalog import DEFAULT_DATA_DIR, EapCatalog, require_private_file

# Decisões reais são privadas (não versionadas): `EAP_ALIASES_PATH` ou `app/data/` ignorado pelo Git.
ALIASES_PATH = Path(os.environ.get("EAP_ALIASES_PATH") or DEFAULT_DATA_DIR / "eap_aliases.json")


class MatchStatus(StrEnum):
    MATCH_CODE_AND_NAME = "MATCH_CODE_AND_NAME"
    MATCH_CODE = "MATCH_CODE"
    MATCH_UNIQUE_NAME = "MATCH_UNIQUE_NAME"
    MATCH_APPROVED_ALIAS = "MATCH_APPROVED_ALIAS"
    REVIEW_NAME_MISMATCH = "REVIEW_NAME_MISMATCH"
    REVIEW_EAP_CATALOG = "REVIEW_EAP_CATALOG"
    REVIEW_MULTIPLE_EAP = "REVIEW_MULTIPLE_EAP"
    UNRESOLVED_UNKNOWN_CODE = "UNRESOLVED_UNKNOWN_CODE"
    UNRESOLVED_GENERIC_VALUE = "UNRESOLVED_GENERIC_VALUE"
    UNRESOLVED_AMBIGUOUS_NAME = "UNRESOLVED_AMBIGUOUS_NAME"


# Únicos status que podem virar vínculo (apply).
SAFE_STATUSES = frozenset(
    {
        MatchStatus.MATCH_CODE_AND_NAME,
        MatchStatus.MATCH_CODE,
        MatchStatus.MATCH_UNIQUE_NAME,
        MatchStatus.MATCH_APPROVED_ALIAS,
    }
)


class EapAliasError(ValueError):
    pass


@dataclass(slots=True, frozen=True)
class ApprovedAlias:
    alias: str
    eap_code: str
    decision: str


@dataclass(slots=True, frozen=True)
class ReconciliationDecisions:
    """Decisões aprovadas e versionadas (`app/data/eap_aliases.json`)."""

    aliases: dict[str, ApprovedAlias] = field(default_factory=dict)
    non_linkable: dict[str, str] = field(default_factory=dict)  # texto normalizado -> motivo


def load_decisions(path: Path = ALIASES_PATH) -> ReconciliationDecisions:
    document = json.loads(require_private_file(path, "EAP_ALIASES_PATH").read_text(encoding="utf-8"))
    if document.get("format_version") != 1:
        raise EapAliasError(f"format_version inesperado em {path}")
    aliases: dict[str, ApprovedAlias] = {}
    for item in document.get("aliases", []):
        key = comparable_eap_name(item["alias"])
        if key in aliases:
            raise EapAliasError(f"alias duplicado: {item['alias']}")
        aliases[key] = ApprovedAlias(item["alias"], item["eap_code"], item["decision"])
    non_linkable: dict[str, str] = {}
    for item in document.get("non_linkable_values", []):
        key = comparable_eap_name(item["value"])
        if key in aliases or key in non_linkable:
            raise EapAliasError(f"valor repetido nas decisões: {item['value']}")
        non_linkable[key] = item["decision"]
    return ReconciliationDecisions(aliases, non_linkable)


def category_of(status: MatchStatus) -> str:
    if status in SAFE_STATUSES:
        return "MATCH"
    return "REVIEW" if status.value.startswith("REVIEW") else "UNRESOLVED"


# Separadores de várias EAPs num mesmo valor ("2108 Destilaria / 2106 Fermentação").
# Só contam quando TODAS as partes são EAP estruturadas.
_MULTI_SEPARATOR_RE = re.compile(r"\s*(?:/|;|\n)\s*")
_ELIGIBLE_LEVELS = frozenset({EapLevel.PROCESS, EapLevel.AREA})


@dataclass(slots=True, frozen=True)
class NameCandidate:
    code: str | None
    name: str
    level: str
    in_review: bool


@dataclass(slots=True)
class ValueReconciliation:
    raw_value: str | None
    status: MatchStatus
    reason: str
    observed_prefix: str | None = None
    parsed_code: str | None = None
    parsed_label: str | None = None
    matched_code: str | None = None
    matched_name: str | None = None
    matched_level: str | None = None
    candidates: list[dict[str, Any]] = field(default_factory=list)

    @property
    def category(self) -> str:
        return category_of(self.status)


class CatalogIndex:
    """Visão de consulta do catálogo versionado: nós carregáveis, códigos em
    revisão e índice de nomes normalizados (incluindo os nomes em revisão,
    para que um nome que aponte para eles nunca vire match)."""

    def __init__(self, catalog: EapCatalog, decisions: ReconciliationDecisions | None = None) -> None:
        decisions = decisions or ReconciliationDecisions()
        self.nodes = {node.code: node for node in catalog.nodes}
        self.names = {node.code: node.name for node in catalog.nodes}
        self.review = {item["code"]: item for item in catalog.review_required if item.get("code")}
        self.by_name: dict[str, list[NameCandidate]] = {}
        for node in catalog.nodes:
            self._add(NameCandidate(node.code, node.name, node.level.value, in_review=False))
        for item in catalog.review_required:
            for name in item.get("names_found", []):
                self._add(NameCandidate(item.get("code"), name, item["level"], in_review=True))
        self.aliases = dict(decisions.aliases)
        self.non_linkable = dict(decisions.non_linkable)
        for key, alias in self.aliases.items():
            # Alias só preenche lacuna: nunca pode competir com um nome oficial
            # nem apontar para nó inexistente, em revisão ou não elegível.
            if key in self.by_name:
                raise EapAliasError(f"alias '{alias.alias}' coincide com um nome oficial do catálogo")
            target = self.nodes.get(alias.eap_code)
            if target is None or target.level not in _ELIGIBLE_LEVELS or alias.eap_code in self.review:
                raise EapAliasError(f"alias '{alias.alias}' aponta para {alias.eap_code}, que não é elegível")

    def _add(self, candidate: NameCandidate) -> None:
        self.by_name.setdefault(comparable_eap_name(candidate.name), []).append(candidate)


def _candidate_dict(candidate: NameCandidate) -> dict[str, Any]:
    return {
        "code": candidate.code,
        "name": candidate.name,
        "level": candidate.level,
        "reviewRequired": candidate.in_review,
    }


def _structured_parts(raw: str) -> list[str]:
    parts = [part for part in _MULTI_SEPARATOR_RE.split(raw) if part.strip()]
    if len(parts) < 2:
        return []
    parsed = [parse_eap_reference(part) for part in parts]
    if all(ref is not None and ref.structured for ref in parsed):
        return parts
    return []


def reconcile_value(raw_value: str | None, index: CatalogIndex) -> ValueReconciliation:
    if raw_value is None or not raw_value.strip():
        return ValueReconciliation(
            raw_value, MatchStatus.UNRESOLVED_GENERIC_VALUE, "Área/EAP vazia no Monday."
        )

    parts = _structured_parts(raw_value)
    if parts:
        resolved = [reconcile_value(part, index) for part in parts]
        codes = {item.parsed_code for item in resolved}
        if len(codes) > 1:
            return ValueReconciliation(
                raw_value,
                MatchStatus.REVIEW_MULTIPLE_EAP,
                f"{len(codes)} EAPs distintas no mesmo valor; o modelo atual tem um único eap_node_id.",
                candidates=[
                    {
                        "raw": item.raw_value,
                        "code": item.parsed_code,
                        "observedPrefix": item.observed_prefix,
                        "status": item.status.value,
                    }
                    for item in resolved
                ],
            )

    reference = parse_eap_reference(raw_value)
    assert reference is not None  # valor não vazio
    if reference.structured:
        code = reference.eap_code
        result = ValueReconciliation(
            raw_value,
            MatchStatus.MATCH_CODE,
            "",
            observed_prefix=reference.eap_prefix,
            parsed_code=code,
            parsed_label=reference.label,
        )
        if code in index.review:
            item = index.review[code]
            result.status = MatchStatus.REVIEW_EAP_CATALOG
            result.reason = f"Código {code} está em EAP_REVIEW_REQUIRED ({item.get('reason')})."
            result.candidates = [{"alternatives": item.get("alternatives", [])}]
            return result
        if code not in index.nodes:
            result.status = MatchStatus.UNRESOLVED_UNKNOWN_CODE
            result.reason = f"Código {code} não existe no catálogo oficial."
            return result
        node = index.nodes[code]
        result.matched_code, result.matched_name, result.matched_level = code, node.name, node.level.value
        issues = check_against_catalog(reference, index.names)
        if any(issue.code is EapIssueCode.EAP_NAME_MISMATCH for issue in issues):
            result.status = MatchStatus.REVIEW_NAME_MISMATCH
            result.reason = (
                f"Código {code} existe, mas o nome '{reference.label}' contradiz o oficial '{node.name}'."
            )
        elif reference.label:
            result.status = MatchStatus.MATCH_CODE_AND_NAME
            result.reason = "Código no catálogo e nome igual ao oficial."
        else:
            result.reason = "Código no catálogo; sem nome no Monday para validar."
        return result

    label = reference.label or raw_value
    if comparable_eap_name(label) in index.non_linkable:
        return ValueReconciliation(
            raw_value,
            MatchStatus.UNRESOLVED_GENERIC_VALUE,
            "Valor genérico aprovado como não vinculável: " + index.non_linkable[comparable_eap_name(label)],
            parsed_label=label,
        )
    candidates = index.by_name.get(comparable_eap_name(label), [])
    eligible = [c for c in candidates if c.level in _ELIGIBLE_LEVELS]
    result = ValueReconciliation(
        raw_value,
        MatchStatus.UNRESOLVED_GENERIC_VALUE,
        "",
        parsed_label=label,
        candidates=[_candidate_dict(c) for c in candidates],
    )
    if len(eligible) > 1:
        result.status = MatchStatus.UNRESOLVED_AMBIGUOUS_NAME
        result.reason = f"Nome corresponde a {len(eligible)} nós oficiais; nenhum é escolhido."
    elif len(eligible) == 1 and eligible[0].in_review:
        result.status = MatchStatus.REVIEW_EAP_CATALOG
        result.parsed_code = eligible[0].code
        result.reason = f"Nome corresponde a {eligible[0].code}, que está em EAP_REVIEW_REQUIRED."
    elif len(eligible) == 1:
        node = index.nodes[eligible[0].code or ""]
        result.status = MatchStatus.MATCH_UNIQUE_NAME
        result.matched_code, result.matched_name, result.matched_level = (
            node.code,
            node.name,
            node.level.value,
        )
        result.reason = "Valor sem código; nome igual a um único nó oficial elegível."
    elif comparable_eap_name(label) in index.aliases:
        alias = index.aliases[comparable_eap_name(label)]
        node = index.nodes[alias.eap_code]
        result.status = MatchStatus.MATCH_APPROVED_ALIAS
        result.matched_code, result.matched_name, result.matched_level = (
            node.code,
            node.name,
            node.level.value,
        )
        result.reason = f"Alias EAP aprovado '{alias.alias}' → {alias.eap_code} (app/data/eap_aliases.json)."
    elif candidates:
        result.reason = "Nome corresponde só a uma ILHA, que não é elegível para equipamento."
    else:
        result.reason = "Valor sem código e sem nó oficial com este nome; não vira EAP."
    return result
