"""Caixa interna persistente do Painel de Equipamentos.

Este serviço não envia e-mails. As gravações de eventos de regressão são
chamadas antes do commit da própria operação de domínio para que sucesso e
notificação sejam atômicos.
"""

from __future__ import annotations

import math
import uuid
from datetime import date

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import CurrentUser
from app.core.errors import NotFoundError
from app.core.permissions import Permission, assert_can
from app.core.scope import allowed_unit_ids, assert_equipment_allowed
from app.models.common import utcnow
from app.models.equipment import STAGES, Equipment, ProjectContext, Unit
from app.models.notification import USER_NOTIFICATION_MODULE, UserNotification
from app.models.user import Role as UserRole
from app.models.user import User
from app.models.workflow_extras import ReopenRequest
from app.modules.equipments.schemas import UserRefOut
from app.modules.notifications.schemas import (
    NotificationPaginationOut,
    PendingReopenApprovalListOut,
    PendingReopenApprovalOut,
    UserNotificationListOut,
    UserNotificationOut,
)


def _user_ref(user: User | None) -> UserRefOut | None:
    if user is None:
        return None
    return UserRefOut(id=user.id, name=user.name, email=user.email)


def _notification_out(item: UserNotification) -> UserNotificationOut:
    equipment = item.equipment
    context = equipment.project_context if equipment is not None else None
    unit = context.unit if context is not None else None
    return UserNotificationOut(
        id=item.id,
        module_key=USER_NOTIFICATION_MODULE,
        event_type=item.event_type,
        equipment_id=item.equipment_id,
        equipment_name=equipment.name if equipment is not None else None,
        project_context_name=context.name if context is not None else None,
        unit_name=unit.name if unit is not None else None,
        reopen_request_id=item.reopen_request_id,
        actor=_user_ref(item.actor),
        title=item.title,
        message=item.message,
        target_url=item.target_url,
        created_at=item.created_at,
        read_at=item.read_at,
    )


async def list_user_notifications(
    session: AsyncSession,
    actor: CurrentUser,
    *,
    page: int,
    page_size: int,
    unread_only: bool,
) -> UserNotificationListOut:
    filters = [
        UserNotification.recipient_user_id == actor.id,
        UserNotification.module_key == USER_NOTIFICATION_MODULE,
    ]
    allowed = await allowed_unit_ids(session, actor)
    if allowed is not None:
        visible_equipment_ids = (
            select(Equipment.id)
            .join(ProjectContext, Equipment.project_context_id == ProjectContext.id)
            .where(ProjectContext.unit_id.in_(allowed))
        )
        filters.append(UserNotification.equipment_id.in_(visible_equipment_ids))
    if unread_only:
        filters.append(UserNotification.read_at.is_(None))

    total = (
        await session.execute(
            select(func.count()).select_from(UserNotification).where(*filters)
        )
    ).scalar_one()
    rows = (
        (
            await session.execute(
                select(UserNotification)
                .options(
                    selectinload(UserNotification.actor),
                    selectinload(UserNotification.equipment)
                    .selectinload(Equipment.project_context)
                    .selectinload(ProjectContext.unit),
                )
                .where(*filters)
                .order_by(UserNotification.created_at.desc(), UserNotification.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .scalars()
        .all()
    )
    return UserNotificationListOut(
        items=[_notification_out(item) for item in rows],
        pagination=NotificationPaginationOut(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=math.ceil(total / page_size) if page_size else 0,
        ),
    )


async def unread_count(session: AsyncSession, actor: CurrentUser) -> int:
    filters = [
        UserNotification.recipient_user_id == actor.id,
        UserNotification.module_key == USER_NOTIFICATION_MODULE,
        UserNotification.read_at.is_(None),
    ]
    allowed = await allowed_unit_ids(session, actor)
    if allowed is not None:
        visible_equipment_ids = (
            select(Equipment.id)
            .join(ProjectContext, Equipment.project_context_id == ProjectContext.id)
            .where(ProjectContext.unit_id.in_(allowed))
        )
        filters.append(UserNotification.equipment_id.in_(visible_equipment_ids))
    return (
        await session.execute(
            select(func.count()).select_from(UserNotification).where(*filters)
        )
    ).scalar_one()


async def mark_read(
    session: AsyncSession, actor: CurrentUser, notification_id: str
) -> UserNotificationOut:
    item = (
        await session.execute(
            select(UserNotification)
            .options(
                selectinload(UserNotification.actor),
                selectinload(UserNotification.equipment)
                .selectinload(Equipment.project_context)
                .selectinload(ProjectContext.unit),
            )
            .where(
                UserNotification.id == notification_id,
                UserNotification.recipient_user_id == actor.id,
                UserNotification.module_key == USER_NOTIFICATION_MODULE,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if item is None:
        raise NotFoundError("Notificação não encontrada")
    if item.equipment_id is not None:
        await assert_equipment_allowed(session, actor, item.equipment_id)
    if item.read_at is None:
        item.read_at = utcnow()
        await session.commit()
    return _notification_out(item)


async def mark_all_read(session: AsyncSession, actor: CurrentUser) -> int:
    filters = [
        UserNotification.recipient_user_id == actor.id,
        UserNotification.module_key == USER_NOTIFICATION_MODULE,
        UserNotification.read_at.is_(None),
    ]
    allowed = await allowed_unit_ids(session, actor)
    if allowed is not None:
        visible_equipment_ids = (
            select(Equipment.id)
            .join(ProjectContext, Equipment.project_context_id == ProjectContext.id)
            .where(ProjectContext.unit_id.in_(allowed))
        )
        filters.append(UserNotification.equipment_id.in_(visible_equipment_ids))
    result = await session.execute(
        update(UserNotification)
        .where(*filters)
        .values(read_at=utcnow())
    )
    await session.commit()
    return int(result.rowcount or 0)


async def list_pending_approvals(
    session: AsyncSession,
    actor: CurrentUser,
    *,
    page: int,
    page_size: int,
) -> PendingReopenApprovalListOut:
    assert_can(actor.role, Permission.WORKFLOW_REOPEN_APPROVE)
    allowed = await allowed_unit_ids(session, actor)
    filters = [ReopenRequest.status == "PENDING"]
    if allowed is not None:
        filters.append(ProjectContext.unit_id.in_(allowed))

    count_stmt = (
        select(func.count())
        .select_from(ReopenRequest)
        .join(Equipment, ReopenRequest.equipment_id == Equipment.id)
        .join(ProjectContext, Equipment.project_context_id == ProjectContext.id)
        .where(*filters)
    )
    total = (await session.execute(count_stmt)).scalar_one()
    requester = User
    rows = (
        await session.execute(
            select(ReopenRequest, Equipment, ProjectContext, Unit, requester)
            .join(Equipment, ReopenRequest.equipment_id == Equipment.id)
            .join(ProjectContext, Equipment.project_context_id == ProjectContext.id)
            .join(Unit, ProjectContext.unit_id == Unit.id)
            .outerjoin(requester, ReopenRequest.requested_by_id == requester.id)
            .where(*filters)
            .order_by(ReopenRequest.requested_at.desc(), ReopenRequest.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    return PendingReopenApprovalListOut(
        items=[
            PendingReopenApprovalOut(
                id=request.id,
                equipment_id=equipment.id,
                equipment_name=equipment.name,
                project_context_name=context.name,
                unit_name=unit.name,
                source_stage=request.source_stage,
                source_stage_label=STAGES[request.source_stage],
                target_stage=request.target_stage,
                target_stage_label=STAGES[request.target_stage],
                justification=request.justification,
                requested_by=_user_ref(requested_by),
                requested_at=request.requested_at,
                target_url=f"/equipamentos/{equipment.id}?reopen={request.id}#reabertura",
            )
            for request, equipment, context, unit, requested_by in rows
        ],
        pagination=NotificationPaginationOut(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=math.ceil(total / page_size) if page_size else 0,
        ),
    )


async def _insert_notifications(
    session: AsyncSession,
    *,
    recipient_ids: list[str],
    actor_user_id: str | None,
    event_type: str,
    equipment_id: str | None,
    reopen_request_id: str | None,
    title: str,
    message: str,
    target_url: str,
    event_key: str,
) -> int:
    if not recipient_ids:
        return 0
    created_at = utcnow()
    rows = [
        {
            "id": str(uuid.uuid4()),
            "recipient_user_id": recipient_id,
            "actor_user_id": actor_user_id,
            "module_key": USER_NOTIFICATION_MODULE,
            "event_type": event_type,
            "equipment_id": equipment_id,
            "reopen_request_id": reopen_request_id,
            "title": title,
            "message": message,
            "target_url": target_url,
            "event_key": event_key,
            "created_at": created_at,
            "read_at": None,
        }
        for recipient_id in sorted(set(recipient_ids))
    ]
    result = await session.execute(
        insert(UserNotification)
        .values(rows)
        .on_conflict_do_nothing(
            index_elements=[
                UserNotification.recipient_user_id,
                UserNotification.event_key,
            ]
        )
        .returning(UserNotification.id)
    )
    return len(result.scalars().all())


_OPERATIONAL_TITLES = {
    "KICKOFF": "Kickoff registrado",
    "FUP": "Acompanhamento da ordem de compra",
    "STARTUP_REMINDER": "Startup próximo",
    "NEGOTIATION_OVERDUE": "Negociação atrasada",
    "DELIVERY_REMINDER": "Prazo de entrega próximo",
    "COMPLETED": "Aquisição concluída",
}


async def notify_operational_event(
    session: AsyncSession,
    *,
    equipment: Equipment,
    event_type: str,
    event_key: str,
    event_date: date | None = None,
) -> int:
    """Espelha eventos operacionais existentes na caixa do responsável.

    Os critérios e prazos continuam pertencendo ao mecanismo atual; esta
    função apenas materializa o evento já reconhecido para o usuário ativo.
    """
    if event_type not in _OPERATIONAL_TITLES or not equipment.responsible_user_id:
        return 0
    recipient = await session.get(User, equipment.responsible_user_id)
    if recipient is None or not recipient.active:
        return 0
    date_line = f"\nData de referência: {event_date.isoformat()}" if event_date else ""
    return await _insert_notifications(
        session,
        recipient_ids=[recipient.id],
        actor_user_id=None,
        event_type=event_type,
        equipment_id=equipment.id,
        reopen_request_id=None,
        title=_OPERATIONAL_TITLES[event_type],
        message=f"Equipamento: {equipment.name}{date_line}",
        target_url=f"/equipamentos/{equipment.id}",
        event_key=f"operational:{event_key}",
    )


async def notify_reopen_requested(
    session: AsyncSession,
    *,
    equipment: Equipment,
    request: ReopenRequest,
    actor: CurrentUser,
) -> int:
    context = await session.get(ProjectContext, equipment.project_context_id)
    unit = await session.get(Unit, context.unit_id) if context is not None else None
    admins = (
        (
            await session.execute(
                select(User.id).where(
                    User.active.is_(True),
                    User.role == UserRole.ADMIN,
                )
            )
        )
        .scalars()
        .all()
    )
    context_name = context.name if context is not None else "Obra não informada"
    unit_name = unit.name if unit is not None else "Unidade não informada"
    message = (
        f"Equipamento: {equipment.name}\n"
        f"Obra: {context_name}\n"
        f"Unidade: {unit_name}\n"
        f"Solicitante: {actor.name}\n"
        f"Fase atual: {request.source_stage} — {STAGES[request.source_stage]}\n"
        f"Fase solicitada: {request.target_stage} — {STAGES[request.target_stage]}\n"
        f"Justificativa: {request.justification}"
    )
    return await _insert_notifications(
        session,
        recipient_ids=list(admins),
        actor_user_id=actor.id,
        event_type="REOPEN_REQUESTED",
        equipment_id=equipment.id,
        reopen_request_id=request.id,
        title="Regressão aguardando aprovação",
        message=message,
        target_url=f"/equipamentos/{equipment.id}?reopen={request.id}#reabertura",
        event_key=f"reopen:{request.id}:requested",
    )


async def notify_reopen_decided(
    session: AsyncSession,
    *,
    equipment: Equipment,
    request: ReopenRequest,
    actor: CurrentUser,
    approved: bool,
) -> int:
    # O administrador que decide a própria solicitação já conhece o resultado;
    # não criamos uma segunda notificação redundante para a mesma pessoa.
    if request.requested_by_id is None or request.requested_by_id == actor.id:
        return 0
    event_type = "REOPEN_APPROVED" if approved else "REOPEN_REJECTED"
    title = "Regressão aprovada" if approved else "Regressão rejeitada"
    result = (
        f"Nova fase: {request.target_stage} — {STAGES[request.target_stage]}"
        if approved
        else f"Fase mantida: {equipment.current_stage} — {STAGES[equipment.current_stage]}"
    )
    note = f"\nNota: {request.decision_note}" if request.decision_note else ""
    message = (
        f"Equipamento: {equipment.name}\n"
        f"Decisão por: {actor.name}\n"
        f"{result}{note}"
    )
    suffix = "approved" if approved else "rejected"
    return await _insert_notifications(
        session,
        recipient_ids=[request.requested_by_id],
        actor_user_id=actor.id,
        event_type=event_type,
        equipment_id=equipment.id,
        reopen_request_id=request.id,
        title=title,
        message=message,
        target_url=f"/equipamentos/{equipment.id}?reopen={request.id}#reabertura",
        event_key=f"reopen:{request.id}:{suffix}",
    )
