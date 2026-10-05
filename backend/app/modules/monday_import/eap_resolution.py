"""Localização da origem → EAP do Hub (P1.3.1).

Fluxo: valor bruto → candidatos (`extract_eap_codes`, prefixo contextual removido)
→ código canônico → validação contra `EapNode` ativo (PROCESS/AREA) → resolvido.
Uma escolha explícita do usuário no mapping (`eapNodes`) prevalece. Nunca há
correspondência por nome, nunca se escolhe entre vários candidatos e nunca se
inventa EAP: o que não resolve fica pendente, com o valor bruto preservado.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.eap import EQUIPMENT_EAP_LEVELS, EapLocationKind, extract_eap_codes
from app.models.equipment import EapNode
from app.modules.monday_import.normalization import canonical_text, clean_text

EapStatus = Literal["RESOLVED", "MULTIPLE", "NONE", "NOT_FOUND"]

# Códigos de issue do plan (não bloqueiam: o equipamento segue com eap_node_id vazio).
EAP_ISSUE_CODES: dict[EapStatus, str] = {
    "MULTIPLE": "MULTIPLE_EAP_CANDIDATES",
    "NONE": "NO_EAP",
    "NOT_FOUND": "EAP_NOT_FOUND",
}
_ISSUE_MESSAGES: dict[EapStatus, str] = {
    "MULTIPLE": "Localização cita mais de uma EAP; nenhuma é escolhida automaticamente.",
    "NONE": "Localização sem código EAP; o equipamento fica sem EAP até um mapeamento.",
    "NOT_FOUND": "Código EAP detectado, mas inexistente ou inativo no catálogo do Hub.",
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

    @property
    def eap_node_id(self) -> str | None:
        return self.node.id if self.node is not None else None

    @property
    def issue_code(self) -> str | None:
        return EAP_ISSUE_CODES.get(self.status)

    @property
    def issue_message(self) -> str | None:
        return _ISSUE_MESSAGES.get(self.status)


class EapResolver:
    """Catálogo ativo carregado uma vez por plan/reconciliação."""

    def __init__(self, nodes: list[EapNodeRef], overrides: dict[str, str] | None = None) -> None:
        self._by_code = {node.code: node for node in nodes}
        self._by_id = {node.id: node for node in nodes}
        self._overrides = dict(overrides or {})  # valor canônico -> eap_node_id (já validado)

    @classmethod
    async def load(cls, session: AsyncSession, overrides: dict[str, str] | None = None) -> EapResolver:
        rows = (
            await session.execute(
                select(EapNode.id, EapNode.code, EapNode.name).where(
                    EapNode.active.is_(True),
                    EapNode.level.in_([level.value for level in EQUIPMENT_EAP_LEVELS]),
                )
            )
        ).all()
        return cls([EapNodeRef(row.id, row.code, row.name) for row in rows], overrides)

    def resolve(self, raw: str | None) -> EapResolution:
        location = extract_eap_codes(clean_text(raw))
        override = self._overrides.get(canonical_text(raw)) if clean_text(raw) else None
        if override is not None and override in self._by_id:
            return EapResolution(raw, "RESOLVED", location.codes, self._by_id[override], from_mapping=True)
        if location.kind is EapLocationKind.NONE:
            return EapResolution(raw, "NONE")
        if location.kind is EapLocationKind.MULTIPLE:
            return EapResolution(raw, "MULTIPLE", location.codes)
        node = self._by_code.get(location.codes[0])
        if node is None:
            return EapResolution(raw, "NOT_FOUND", location.codes)
        return EapResolution(raw, "RESOLVED", location.codes, node)
