"""Localização da origem → EAP do Hub.

Fluxo: valor bruto → candidatos (`extract_eap_codes`, prefixo contextual removido)
→ código canônico → decisão de catálogo (`catalog_taxonomy.decide_eap`).

Uma escolha explícita do usuário no mapping (`eapNodes`) prevalece e resulta em
EXISTING. Sem ela, a EAP só é casada pelo código canônico, nunca pelo nome.
Nunca se escolhe entre vários candidatos. EAP nova só vira CREATE quando há
código, nome e pai (para AREA) inequívocos; caso contrário fica UNRESOLVED com
o valor bruto preservado.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.eap import EQUIPMENT_EAP_LEVELS, EapLocationKind, extract_eap_codes, parse_eap_reference
from app.models.equipment import EapNode
from app.modules.monday_import.catalog_evidence import CatalogEvidence, EvidenceLookup, EvidenceSource
from app.modules.monday_import.catalog_taxonomy import (
    CatalogAction,
    EapCatalogEntry,
    EapDecision,
    EapNodeSpec,
    codes_by_eap_name,
    decide_eap,
    reliable_eap_label,
)
from app.modules.monday_import.normalization import canonical_text, clean_text

# RESOLVED: EAP existente e única. CREATE/CONFLICT/UNRESOLVED vêm da taxonomia.
# NONE/MULTIPLE/NOT_FOUND são mantidos por compatibilidade com consumidores existentes.
EapStatus = Literal["RESOLVED", "CREATE", "CONFLICT", "UNRESOLVED", "MULTIPLE", "NONE", "NOT_FOUND"]

_ISSUE_STATUS: dict[str, EapStatus] = {
    "NO_EAP": "NONE",
    "MULTIPLE_EAP_CANDIDATES": "MULTIPLE",
    "EAP_NOT_FOUND": "NOT_FOUND",
}


@dataclass(slots=True, frozen=True)
class EapNodeRef:
    id: str
    code: str
    name: str


@dataclass(slots=True, frozen=True)
class EapResolution:
    raw: str | None
    status: EapStatus
    codes: tuple[str, ...] = ()
    node: EapNodeRef | None = None
    from_mapping: bool = False
    decision: EapDecision | None = None
    creates: tuple[EapNodeSpec, ...] = field(default=())

    @property
    def eap_node_id(self) -> str | None:
        """Só EXISTING/mapping têm id. CREATE grava vínculo após o apply criar o nó."""
        return self.node.id if self.node is not None else None

    @property
    def issue_code(self) -> str | None:
        return self.decision.issue_code if self.decision is not None else None

    @property
    def issue_message(self) -> str | None:
        return self.decision.message if self.decision is not None else None


class EapResolver:
    """Catálogo de EAP carregado uma vez por plan/reconciliação.

    Carrega inclusive nós inativos, para que um código inativo nunca seja
    tratado como "novo" (violaria a unicidade de `eap_node.code`).
    """

    def __init__(
        self,
        catalog: list[EapCatalogEntry],
        overrides: dict[str, str] | None = None,
        evidence: CatalogEvidence | None = None,
    ) -> None:
        self._catalog = {entry.code: entry for entry in catalog}
        self._by_id = {
            entry.id: EapNodeRef(entry.id, entry.code, entry.name) for entry in catalog if entry.active
        }
        self._overrides = dict(overrides or {})  # valor canônico -> eap_node_id (já validado)
        # Evidências agregadas (Monday de todos os registros, árvore EAP, LGE, manual).
        # Sem elas, só o rótulo da própria célula vale como evidência MONDAY.
        self._evidence = evidence
        self._codes_by_name = codes_by_eap_name(self._catalog)

    @classmethod
    async def load(
        cls,
        session: AsyncSession,
        overrides: dict[str, str] | None = None,
        evidence: CatalogEvidence | None = None,
    ) -> EapResolver:
        rows = (
            await session.execute(
                select(EapNode.id, EapNode.code, EapNode.name, EapNode.level, EapNode.active).where(
                    EapNode.level.in_([level.value for level in EQUIPMENT_EAP_LEVELS])
                )
            )
        ).all()
        catalog = [
            EapCatalogEntry(id=row.id, code=row.code, name=row.name, level=row.level, active=row.active)
            for row in rows
        ]
        return cls(catalog, overrides, evidence)

    def resolve(self, raw: str | None) -> EapResolution:
        text = clean_text(raw)
        location = extract_eap_codes(text)

        override = self._overrides.get(canonical_text(raw)) if text else None
        if override is not None and override in self._by_id:
            node = self._by_id[override]
            decision = EapDecision(CatalogAction.EXISTING, code=node.code, node_id=node.id)
            return EapResolution(raw, "RESOLVED", location.codes, node, from_mapping=True, decision=decision)

        label = None
        if location.kind is EapLocationKind.SINGLE and text is not None:
            reference = parse_eap_reference(text)
            label = reference.label if reference is not None else None

        decision = decide_eap(
            location.codes,
            label,
            self._catalog,
            self._name_lookup(location.codes, label),
            codes_by_name=self._codes_by_name,
        )
        status = self._status_for(decision)
        existing_node: EapNodeRef | None = None
        if decision.action is CatalogAction.EXISTING and decision.node_id is not None:
            existing_node = self._by_id.get(decision.node_id)
        return EapResolution(
            raw, status, location.codes, existing_node, decision=decision, creates=decision.creates
        )

    def _name_lookup(self, codes: tuple[str, ...], label: str | None) -> Callable[[str], EvidenceLookup]:
        if self._evidence is not None:
            return self._evidence.eap_name
        own_code = codes[0] if len(codes) == 1 else None
        own_label = reliable_eap_label(label)

        def lookup(code: str) -> EvidenceLookup:
            if code == own_code and own_label:
                return EvidenceLookup(value=own_label, source=EvidenceSource.MONDAY)
            return EvidenceLookup()

        return lookup

    @staticmethod
    def _status_for(decision: EapDecision) -> EapStatus:
        if decision.action is CatalogAction.EXISTING:
            return "RESOLVED"
        if decision.action is CatalogAction.CREATE:
            return "CREATE"
        if decision.action is CatalogAction.CONFLICT:
            return "CONFLICT"
        return _ISSUE_STATUS.get(decision.issue_code or "", "UNRESOLVED")
