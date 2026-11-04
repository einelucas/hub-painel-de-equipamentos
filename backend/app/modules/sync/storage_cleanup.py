"""Recuperação da outbox de arquivos removidos por exclusões em cascata."""

from __future__ import annotations

import logging

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.storage import get_contract_file_storage
from app.models.sync import ContractFileCleanup

logger = logging.getLogger(__name__)


async def recover_contract_file_cleanups(*, limit: int = 200) -> int:
    """Reexecuta limpezas pendentes sem comprometer a transação de domínio.

    A remoção dos objetos é idempotente nos providers suportados. A linha só
    sai da outbox depois que o storage confirma a exclusão.
    """
    storage = get_contract_file_storage()
    completed = 0
    async with SessionLocal() as session:
        cleanups = list(
            (
                await session.execute(
                    select(ContractFileCleanup)
                    .order_by(ContractFileCleanup.created_at.asc())
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
        for cleanup in cleanups:
            try:
                await storage.delete(cleanup.storage_key)
                await session.delete(cleanup)
                completed += 1
            except Exception as exc:  # pragma: no cover - depende do provider externo
                cleanup.last_error = str(exc)[:2000]
                logger.warning("contract cleanup still pending key=%s: %s", cleanup.storage_key, exc)
        await session.commit()
    return completed
