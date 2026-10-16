"""Helper compartilhado de auditoria. Nunca armazena senhas, tokens ou segredos."""

from __future__ import annotations

import uuid
from typing import Any, cast

from sqlalchemy import ColumnElement, Table, and_, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.common import utcnow
from app.models.equipment import EquipmentComponent
from app.models.process import Contract, LegalProcess, Negotiation, PurchaseOrder, PurchaseRequest

_SENSITIVE_KEYS = {"password", "passwordhash", "token", "secret", "senha"}

# GAP-002/GAP-019 (Etapa 6D): sub-entidades 1:1 do equipamento cujos
# AuditLogs de migração (`monday_import/apply.py`) têm `entityId` da própria
# sub-entidade e nenhum `metadata.equipmentId` — só resolvíveis por
# relacionamento. Usado tanto pelo histórico do equipamento
# (`workflow/services.py::history`) quanto pelo filtro `equipmentId` da
# Auditoria (`audit/services.py::list_audit_logs`), para as duas telas nunca
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


# Limite de parâmetros de bind por statement do protocolo Postgres/asyncpg.
_MAX_BIND_PARAMS = 32767


def chunk_size_for(columns: int, *, preferred: int = 1000) -> int:
    """Linhas por INSERT multi-VALUES sem estourar o limite de binds do asyncpg."""
    return max(1, min(preferred, (_MAX_BIND_PARAMS - 1) // max(1, columns)))


def build_audit_row(
    *,
    action: str,
    entity: str,
    user_id: str | None = None,
    entity_id: str | None = None,
    previous_data: Any = None,
    new_data: Any = None,
    metadata: Any = None,
) -> dict[str, Any]:
    """Mesmos campos que `record_audit` preencheria, como linha de tabela
    (nomes de coluna) para `bulk_insert_audit`. Não toca na sessão."""
    return {
        "id": str(uuid.uuid4()),
        "userId": user_id,
        "action": action,
        "entity": entity,
        "entityId": entity_id,
        "previousData": _redact(previous_data),
        "newData": _redact(new_data),
        "metadata": _redact(metadata),
        "createdAt": utcnow(),
    }


async def bulk_insert_audit(
    session: AsyncSession, rows: list[dict[str, Any]], *, chunk_size: int | None = None
) -> int:
    """Insere linhas de `build_audit_row` em INSERTs multi-VALUES por lote
    (um round-trip por lote, sem flush do ORM). Retorna o nº de statements."""
    if not rows:
        return 0
    table = cast(Table, AuditLog.__table__)
    size = chunk_size or chunk_size_for(len(table.columns))
    statements = 0
    for start in range(0, len(rows), size):
        await session.execute(insert(table).values(rows[start : start + size]))
        statements += 1
    return statements
