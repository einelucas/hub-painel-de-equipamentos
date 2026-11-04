"""Fan-out local alimentado pelo log persistente de eventos.

Cada processo consulta o PostgreSQL uma única vez por intervalo e distribui os
eventos para suas conexões SSE. Como a origem é a tabela ``sync_event``, workers
e instâncias diferentes observam os mesmos commits sem depender de memória
compartilhada ou de infraestrutura adicional.
"""

from __future__ import annotations

import asyncio

from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.models.sync import SyncEvent

Subscriber = asyncio.Queue[SyncEvent | None]


class SyncEventBroker:
    def __init__(self, *, interval_seconds: float = 0.75) -> None:
        self._interval = interval_seconds
        self._cursor: int | None = None
        self._subscribers: set[Subscriber] = set()
        self._task: asyncio.Task[None] | None = None

    def subscribe(self) -> Subscriber:
        queue: Subscriber = asyncio.Queue(maxsize=500)
        self._subscribers.add(queue)
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run(), name="sync-event-broker")
        return queue

    def unsubscribe(self, queue: Subscriber) -> None:
        self._subscribers.discard(queue)

    async def _run(self) -> None:
        try:
            if self._cursor is None:
                async with SessionLocal() as session:
                    self._cursor = int(
                        (await session.scalar(select(func.coalesce(func.max(SyncEvent.id), 0)))) or 0
                    )
            while self._subscribers:
                async with SessionLocal() as session:
                    items = list(
                        (
                            await session.execute(
                                select(SyncEvent)
                                .where(SyncEvent.id > self._cursor)
                                .order_by(SyncEvent.id.asc())
                                .limit(500)
                            )
                        )
                        .scalars()
                        .all()
                    )
                if not items:
                    await asyncio.sleep(self._interval)
                    continue
                for item in items:
                    self._cursor = item.id
                    for queue in tuple(self._subscribers):
                        if queue.full():
                            # Cliente lento: força reconexão. O cursor enviado
                            # pelo cliente recupera os eventos perdidos do log.
                            while not queue.empty():
                                queue.get_nowait()
                            queue.put_nowait(None)
                            continue
                        queue.put_nowait(item)
        finally:
            self._task = None
            if not self._subscribers:
                # No próximo assinante, parte do MAX atual e o catch-up da
                # própria conexão cobre a janela sem assinantes.
                self._cursor = None


sync_event_broker = SyncEventBroker()
