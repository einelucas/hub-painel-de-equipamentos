"""Etapa 7F — geração de eventos Kickoff/FUP ao concluir fases 5 e 7.

Nunca bloqueia a transição de fase real: é chamado DEPOIS do commit que
mudou `current_stage`, numa operação separada. Falha no envio (adapter) fica
registrada no próprio evento (`status=FAILED` + `failure_reason`) — nunca
propaga como erro para quem pediu o avanço de fase.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser
from app.core.scope import assert_equipment_allowed
from app.models.common import utcnow
from app.models.equipment import Equipment, WorkflowTransition
from app.models.notification import NotificationEvent
from app.models.user import User
from app.modules.notifications.adapter import get_notification_adapter
from app.modules.notifications.schemas import NotificationEventListOut, NotificationEventOut

logger = logging.getLogger("app.notifications")

# from_stage da transição -> tipo de evento gerado ao concluir aquela fase.
_TRIGGER_KIND_BY_FROM_STAGE: dict[int, str] = {5: "KICKOFF", 7: "FUP"}

_SUBJECT_BY_KIND: dict[str, str] = {
    "KICKOFF": "Kickoff — contrato escriturado",
    "FUP": "FUP — Ordem de Compra aprovada",
}


async def _resolve_recipients(session: AsyncSession, equipment: Equipment) -> list[str]:
    """Responsável resolvido via `User` existente. Superiores dependem de um
    provedor de hierarquia corporativa (Microsoft/Automação) ainda não
    definido — fica como lista vazia até essa decisão, nunca hardcoded."""
    recipients: list[str] = []
    if equipment.responsible_user_id:
        user = (
            await session.execute(select(User).where(User.id == equipment.responsible_user_id))
        ).scalar_one_or_none()
        if user is not None:
            recipients.append(user.email)
    # TODO(pendência de infra): resolver superiores do responsável quando o
    # time de Automação definir a fonte (Microsoft Graph ou equivalente).
    return recipients


async def trigger_for_transition(
    session: AsyncSession, *, equipment: Equipment, transition: WorkflowTransition
) -> NotificationEvent | None:
    kind = _TRIGGER_KIND_BY_FROM_STAGE.get(transition.from_stage)
    if kind is None:
        return None

    try:
        async with session.begin_nested():
            event = NotificationEvent(
                equipment_id=equipment.id,
                workflow_transition_id=transition.id,
                kind=kind,
                status="PENDING",
            )
            session.add(event)
            await session.flush()
    except IntegrityError:
        # Idempotência: já existe um evento deste tipo para esta transição
        # (retry, ou o gatilho foi chamado mais de uma vez) — não duplica.
        return None

    recipients = await _resolve_recipients(session, equipment)
    event.recipient_summary = ", ".join(recipients) if recipients else "(sem destinatário resolvido)"
    adapter = get_notification_adapter()
    try:
        await adapter.send(
            subject=_SUBJECT_BY_KIND[kind],
            body=f"Equipamento {equipment.name} — fase concluída.",
            recipients=recipients,
        )
    except Exception as exc:  # noqa: BLE001 — falha de envio nunca deve propagar
        event.status = "FAILED"
        event.failure_reason = str(exc)
        logger.warning("notification.send_failed", extra={"eventId": event.id, "error": str(exc)})
    else:
        event.status = "SENT"
        event.sent_at = utcnow()

    await session.commit()
    return event


def _out(item: NotificationEvent) -> NotificationEventOut:
    return NotificationEventOut(
        id=item.id,
        equipment_id=item.equipment_id,
        workflow_transition_id=item.workflow_transition_id,
        kind=item.kind,
        status=item.status,
        recipient_summary=item.recipient_summary,
        failure_reason=item.failure_reason,
        created_at=item.created_at,
        sent_at=item.sent_at,
    )


async def list_notifications(
    session: AsyncSession, equipment_id: str, actor: CurrentUser
) -> NotificationEventListOut:
    await assert_equipment_allowed(session, actor, equipment_id)
    rows = (
        (
            await session.execute(
                select(NotificationEvent)
                .where(NotificationEvent.equipment_id == equipment_id)
                .order_by(NotificationEvent.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return NotificationEventListOut(items=[_out(row) for row in rows])
