"""Serviço de auditoria compartilhado do Hub."""

from __future__ import annotations

from datetime import date, datetime, time

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.equipment import Equipment, EquipmentComponent, ProjectContext
from app.models.process import Contract, LegalProcess, Negotiation, PurchaseOrder, PurchaseRequest
from app.models.user import User
from app.shared.audit import equipment_audit_conditions


async def list_audit_logs(
    session: AsyncSession,
    *,
    page: int,
    page_size: int,
    entity: str | None = None,
    action: str | None = None,
    equipment_id: str | None = None,
    user_id: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    allowed_units: set[str] | None = None,
) -> tuple[list[AuditLog], int, dict[str, User]]:
    filters = []
    if allowed_units is not None:
        equipment_ids = (
            select(Equipment.id)
            .join(ProjectContext, Equipment.project_context_id == ProjectContext.id)
            .where(ProjectContext.unit_id.in_(allowed_units))
        )
        scoped_conditions = [
            and_(AuditLog.entity == "Equipment", AuditLog.entityId.in_(equipment_ids)),
            AuditLog.metadata_["equipmentId"].astext.in_(equipment_ids),
            and_(
                AuditLog.entity == "EquipmentComponent",
                AuditLog.entityId.in_(
                    select(EquipmentComponent.id).where(
                        EquipmentComponent.equipment_id.in_(equipment_ids)
                    )
                ),
            ),
        ]
        for model in (Negotiation, LegalProcess, Contract, PurchaseRequest, PurchaseOrder):
            scoped_conditions.append(
                and_(
                    AuditLog.entity == model.__name__,
                    AuditLog.entityId.in_(
                        select(model.id).where(model.equipment_id.in_(equipment_ids))
                    ),
                )
            )
        filters.append(or_(*scoped_conditions))
    if entity:
        filters.append(AuditLog.entity == entity)
    if action:
        filters.append(AuditLog.action == action)
    if equipment_id:
        # GAP-019 (Etapa 6D): mesma lógica de relacionamento do GAP-002
        # (histórico do equipamento) — inclui sub-entidades (componentes,
        # negociação, jurídico, contrato, SC/OCI) sem reescrever histórico.
        filters.append(or_(*await equipment_audit_conditions(session, equipment_id)))
    if user_id:
        filters.append(AuditLog.userId == user_id)
    if date_from:
        filters.append(AuditLog.createdAt >= datetime.combine(date_from, time.min))
    if date_to:
        filters.append(AuditLog.createdAt <= datetime.combine(date_to, time.max))

    stmt = select(AuditLog).order_by(AuditLog.createdAt.desc())
    count_stmt = select(func.count()).select_from(AuditLog)
    for condition in filters:
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)

    result = await session.execute(stmt)
    logs = list(result.scalars().all())
    total = (await session.execute(count_stmt)).scalar_one()

    user_ids = {log.userId for log in logs if log.userId is not None}
    users: dict[str, User] = {}
    if user_ids:
        users_result = await session.execute(select(User).where(User.id.in_(user_ids)))
        users = {u.id: u for u in users_result.scalars().all()}

    return logs, total, users
