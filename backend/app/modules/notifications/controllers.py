"""Notificações por equipamento e administração da central de e-mails."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, require_permission
from app.core.database import get_session
from app.core.permissions import Permission
from app.models.notification import EmailDelivery
from app.modules.notifications import mail_service, services
from app.modules.notifications.schemas import (
    MailDeliveryListOut,
    MailDeliveryOut,
    MailProcessOut,
    MailRuleListOut,
    MailRuleOut,
    MailRuleUpdate,
    MailSettingsOut,
    MailTestIn,
    NotificationEventListOut,
)

router = APIRouter(tags=["notificacoes"])
_admin = require_permission(Permission.USERS_MANAGE)


@router.get("/equipments/{equipment_id}/notifications", response_model=NotificationEventListOut)
async def get_notifications(
    equipment_id: str,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(require_permission(Permission.EQUIPMENTS_READ)),
) -> NotificationEventListOut:
    return await services.list_notifications(session, equipment_id, actor)


@router.get("/notifications/settings", response_model=MailSettingsOut)
async def settings(_: CurrentUser = Depends(_admin)) -> MailSettingsOut:
    return MailSettingsOut.model_validate(mail_service.settings_summary())


@router.get("/notifications/rules", response_model=MailRuleListOut)
async def rules(
    session: AsyncSession = Depends(get_session),
    _: CurrentUser = Depends(_admin),
) -> MailRuleListOut:
    return MailRuleListOut(items=await mail_service.list_rules(session))


@router.put("/notifications/rules/{kind}", response_model=MailRuleOut)
async def save_rule(
    kind: str,
    body: MailRuleUpdate,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(_admin),
) -> MailRuleOut:
    return await mail_service.update_rule(session, actor, kind, body)


@router.get("/notifications/deliveries", response_model=MailDeliveryListOut)
async def deliveries(
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
    _: CurrentUser = Depends(_admin),
) -> MailDeliveryListOut:
    rows = (await session.execute(
        select(EmailDelivery).order_by(EmailDelivery.created_at.desc()).limit(limit)
    )).scalars().all()
    return MailDeliveryListOut(items=[mail_service.public_delivery(row) for row in rows])


@router.post("/notifications/test", response_model=MailDeliveryOut)
async def test_mail(
    body: MailTestIn,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(_admin),
) -> MailDeliveryOut:
    item = await mail_service.enqueue_test(
        session, actor, body.subject, body.body, provider=body.provider
    )
    await mail_service.deliver_pending(only_id=item.id)
    await session.refresh(item)
    return mail_service.public_delivery(item)


@router.post("/notifications/process", response_model=MailProcessOut)
async def process_mail(_: CurrentUser = Depends(_admin)) -> MailProcessOut:
    scheduled = await mail_service.enqueue_startup_reminders_in_new_session()
    processed = await mail_service.deliver_pending()
    return MailProcessOut(scheduled=scheduled, processed=processed)


@router.post("/notifications/deliveries/{delivery_id}/retry", response_model=MailDeliveryOut)
async def retry(
    delivery_id: str,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(_admin),
) -> MailDeliveryOut:
    return await mail_service.retry_delivery(session, actor, delivery_id)
