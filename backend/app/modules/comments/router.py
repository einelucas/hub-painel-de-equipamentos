from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, require_permission
from app.core.database import get_session
from app.core.permissions import Permission
from app.modules.comments import service
from app.modules.comments.schemas import CommentCreateIn, CommentListOut, CommentOut, CommentUpdateIn

router = APIRouter(tags=["comentarios"])

# Etapa 7E: ler comentários é consulta normal (inclui Jurídico/Suprimentos);
# escrever reaproveita a mesma permissão de dados de processo
# (Engenharia/Planejamento) — nenhuma permissão nova só para isso.
_read = require_permission(Permission.EQUIPMENTS_READ)
_write = require_permission(Permission.PROCESS_WRITE)


@router.get("/equipments/{equipment_id}/comments", response_model=CommentListOut)
async def get_comments(
    equipment_id: str,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(_read),
) -> CommentListOut:
    return await service.list_comments(session, equipment_id, actor)


@router.post(
    "/equipments/{equipment_id}/comments", response_model=CommentOut, status_code=status.HTTP_201_CREATED
)
async def post_comment(
    equipment_id: str,
    body: CommentCreateIn,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(_write),
) -> CommentOut:
    return await service.create_comment(session, equipment_id, text=body.text, actor=actor)


@router.patch("/equipments/{equipment_id}/comments/{comment_id}", response_model=CommentOut)
async def patch_comment(
    equipment_id: str,
    comment_id: str,
    body: CommentUpdateIn,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(_write),
) -> CommentOut:
    return await service.update_comment(
        session, equipment_id, comment_id, text=body.text, actor=actor
    )


@router.delete(
    "/equipments/{equipment_id}/comments/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    response_class=Response,
)
async def delete_comment(
    equipment_id: str,
    comment_id: str,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(_write),
) -> None:
    await service.delete_comment(session, equipment_id, comment_id, actor)
