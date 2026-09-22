"""Helper compartilhado de auditoria. Nunca armazena senhas, tokens ou segredos."""

from __future__ import annotations

from typing import Any

from sqlalchemy import ColumnElement, and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.equipment import EquipmentComponent
from app.models.process import Contract, LegalProcess, Negotiation, PurchaseOrder, PurchaseRequest

_SENSITIVE_KEYS = {"password", "passwordhash", "token", "secret", "senha"}

# GAP-002/GAP-019 (Etapa 6D): sub-entidades 1:1 do equipamento cujos
# AuditLogs de migração (`monday_import/apply.py`) têm `entityId` da própria
# sub-entidade e nenhum `metadata.equipmentId` — só resolvíveis por
# relacionamento. Usado tanto pelo histórico do equipamento
# (`workflow/service.py::history`) quanto pelo filtro `equipmentId` da
# Auditoria (`audit/service.py::list_audit_logs`), para as duas telas nunca
# divergirem em "o que conta como AuditLog deste equipamento".
_EQUIPMENT_SUB_ENTITY_MODELS = (Negotiation, LegalProcess, Contract, PurchaseRequest, PurchaseOrder)


async def equipment_audit_conditions(
    session: AsyncSession, equipment_id: str
) -> list[ColumnElement[bool]]:
    """Todas as condições (para `or_(*conditions)`) que identificam um
    AuditLog como pertencente a este equipamento: o próprio Equipment, seus
    EquipmentComponent, e as sub-entidades 1:1 do processo. Nenhum dado é
    reescrito — só leitura, resolvida pela FK real de cada sub-entidade."""
    conditions: list[ColumnElement[bool]] = [
        AuditLog.entityId == equipment_id,
        AuditLog.metadata_["equipmentId"].astext == equipment_id,
    ]

    component_ids = (
        (
            await session.execute(
                select(EquipmentComponent.id).where(
                    EquipmentComponent.equipment_id == equipment_id
                )
            )
        )
        .scalars()
        .all()
    )
    if component_ids:
        conditions.append(
            and_(AuditLog.entity == "EquipmentComponent", AuditLog.entityId.in_(component_ids))
        )

    for model in _EQUIPMENT_SUB_ENTITY_MODELS:
        sub_entity_id = (
            await session.execute(select(model.id).where(model.equipment_id == equipment_id))
        ).scalar_one_or_none()
        if sub_entity_id is not None:
            conditions.append(
                and_(AuditLog.entity == model.__name__, AuditLog.entityId == sub_entity_id)
            )

    return conditions


def _redact(value: Any) -> Any:
    if value is None or not isinstance(value, dict | list):
        return value
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return {
        key: ("[REDACTED]" if key.lower() in _SENSITIVE_KEYS else _redact(val))
        for key, val in value.items()
    }


async def record_audit(
    session: AsyncSession,
    *,
    action: str,
    entity: str,
    user_id: str | None = None,
    entity_id: str | None = None,
    previous_data: Any = None,
    new_data: Any = None,
    metadata: Any = None,
) -> None:
    session.add(
        AuditLog(
            userId=user_id,
            action=action,
            entity=entity,
            entityId=entity_id,
            previousData=_redact(previous_data),
            newData=_redact(new_data),
            metadata_=_redact(metadata),
        )
    )
    await session.flush()
