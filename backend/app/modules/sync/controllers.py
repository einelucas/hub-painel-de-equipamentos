from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, require_permission
from app.core.database import SessionLocal, get_session
from app.core.permissions import Permission
from app.core.scope import allowed_unit_ids
from app.modules.sync import services
from app.modules.sync.broker import sync_event_broker
from app.modules.sync.schemas import SyncEventListOut, SyncEventOut

router = APIRouter(prefix="/sync", tags=["sincronização"])


@router.get("/events", response_model=SyncEventListOut)
async def get_sync_events(
    after: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(require_permission(Permission.EQUIPMENTS_READ)),
) -> SyncEventListOut:
    items = await services.list_events(session, actor, after=after, limit=limit)
    return SyncEventListOut(
        items=[SyncEventOut.model_validate(item) for item in items],
        cursor=items[-1].id if items else after,
    )


def _sse(event: SyncEventOut) -> str:
    data = json.dumps(jsonable_encoder(event), ensure_ascii=False, separators=(",", ":"))
    return f"id: {event.id}\nevent: change\ndata: {data}\n\n"


@router.get("/events/stream")
async def stream_sync_events(
    request: Request,
    after: int = Query(default=0, ge=0),
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    actor: CurrentUser = Depends(require_permission(Permission.EQUIPMENTS_READ)),
) -> StreamingResponse:
    try:
        cursor = max(after, int(last_event_id or 0))
    except ValueError:
        cursor = after

    async def generate() -> AsyncIterator[str]:
        nonlocal cursor
        queue = sync_event_broker.subscribe()
        yield "retry: 2000\n\n"
        try:
            # Catch-up persistente: cobre desconexões, troca de worker e a
            # janela entre a assinatura local e o início da leitura.
            async with SessionLocal() as session:
                scope = await allowed_unit_ids(session, actor)
                while True:
                    items = await services.list_events(session, actor, after=cursor, limit=500)
                    for item in items:
                        cursor = item.id
                        yield _sse(SyncEventOut.model_validate(item))
                    if len(items) < 500:
                        break

            # Reconecta periodicamente para revalidar identidade e escopo.
            reconnect_at = time.monotonic() + 55
            while not await request.is_disconnected():
                remaining = reconnect_at - time.monotonic()
                if remaining <= 0:
                    break
                try:
                    queued = await asyncio.wait_for(queue.get(), timeout=min(15, remaining))
                except TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                if queued is None:
                    break
                if queued.id <= cursor:
                    continue
                cursor = queued.id
                if scope is None or queued.unit_id in scope:
                    yield _sse(SyncEventOut.model_validate(queued))
        finally:
            sync_event_broker.unsubscribe(queue)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
