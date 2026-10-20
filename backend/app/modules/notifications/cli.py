"""Worker periódico (Railway cron): python -m app.modules.notifications.cli.

Configure execução horária e NOTIFICATION_MODE. Não execute duas vezes em
paralelo: a fila aplica SKIP LOCKED e chaves idempotentes.
"""

from __future__ import annotations

import asyncio
import logging

from app.modules.notifications.mail_service import (
    deliver_pending,
    enqueue_startup_reminders_in_new_session,
    mark_stale_processing,
)

logger = logging.getLogger(__name__)


async def main() -> None:
    stale = await mark_stale_processing()
    scheduled = await enqueue_startup_reminders_in_new_session()
    processed = await deliver_pending(limit=100)
    logger.info(
        "notification worker completed stale=%s scheduled=%s processed=%s",
        stale, scheduled, processed,
    )


if __name__ == "__main__":
    asyncio.run(main())
