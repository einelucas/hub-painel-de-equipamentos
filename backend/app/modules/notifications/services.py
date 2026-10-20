"""Etapa 7F — geração de eventos Kickoff/FUP ao concluir fases 5 e 7.

Nunca bloqueia a transição de fase real: é chamado DEPOIS do commit que
mudou `current_stage`, numa operação separada. Falha no envio (adapter) fica
registrada no próprio evento (`status=FAILED` + `failure_reason`) — nunca
propaga como erro para quem pediu o avanço de fase.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser
from app.core.scope import assert_equipment_allowed
from app.models.equipment import Equipment, WorkflowTransition
from app.models.notification import NotificationEvent
from app.modules.notifications.schemas import NotificationEventListOut, NotificationEventOut

logger = logging.getLogger("app.notifications")

# from_stage da transição -> tipo de evento gerado ao concluir aquela fase.
_TRIGGER_KIND_BY_FROM_STAGE: dict[int, str] = {5: "KICKOFF", 7: "FUP"}



async def trigger_for_transition(
    session: AsyncSession, *, equipment: Equipment, transition: WorkflowTransition
) -> NotificationEvent | None:
    """Persiste evento e outbox; nunca finge envio SMTP/Graph nesta transição."""
    kind = _TRIGGER_KIND_BY_FROM_STAGE.get(transition.from_stage)
    if kind is None:
        return None
    from app.modules.notifications.mail_service import enqueue_equipment, enqueue_transition

    try:
        event = await enqueue_transition(session, equipment, transition, kind)
        if transition.from_stage == 7:
            await enqueue_equipment(
                session, equipment, "COMPLETED", f"transition:{transition.id}:COMPLETED"
            )
        await session.commit()
    except Exception:
        await session.rollback()
        logger.exception("notification enqueue failed transition=%s", transition.id)
        return None
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
