"""Etapa 7E — comentários do equipamento.

Conceito à parte de `WorkflowTransition`/`OperationalStatusEvent`: é uma
conversa sobre o equipamento, não uma mudança de fase nem de estado
operacional. Não vira `AuditLog` — comentário não é uma mudança de dado do
processo, é comunicação entre pessoas.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.auth import CurrentUser
from app.core.errors import DomainError, NotFoundError
from app.core.permissions import Role
from app.core.scope import assert_equipment_allowed
from app.models.workflow_extras import Comment
from app.modules.comments.schemas import CommentListOut, CommentOut
from app.modules.equipments.schemas import UserRefOut


def _out(item: Comment) -> CommentOut:
    return CommentOut(
        id=item.id,
        equipment_id=item.equipment_id,
        text=item.text,
        author=(
            UserRefOut(id=item.author.id, name=item.author.name, email=item.author.email)
            if item.author
            else None
        ),
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


async def list_comments(
    session: AsyncSession, equipment_id: str, actor: CurrentUser
) -> CommentListOut:
    await assert_equipment_allowed(session, actor, equipment_id)
    rows = (
        (
            await session.execute(
                select(Comment)
                .options(joinedload(Comment.author))
                .where(Comment.equipment_id == equipment_id)
                .order_by(Comment.created_at)
            )
        )
        .scalars()
        .all()
    )
    return CommentListOut(items=[_out(row) for row in rows])


async def create_comment(
    session: AsyncSession, equipment_id: str, *, text: str, actor: CurrentUser
) -> CommentOut:
    await assert_equipment_allowed(session, actor, equipment_id)
    item = Comment(equipment_id=equipment_id, text=text.strip(), author_user_id=actor.id)
    session.add(item)
    await session.flush()
    await session.commit()
    row = (
        await session.execute(
            select(Comment).options(joinedload(Comment.author)).where(Comment.id == item.id)
        )
    ).scalar_one()
    return _out(row)


async def _get_comment(session: AsyncSession, equipment_id: str, comment_id: str) -> Comment:
    item = (
        await session.execute(
            select(Comment)
            .options(joinedload(Comment.author))
            .where(Comment.id == comment_id, Comment.equipment_id == equipment_id)
        )
    ).scalar_one_or_none()
    if item is None:
        raise NotFoundError("Comentário não encontrado")
    return item


async def update_comment(
    session: AsyncSession, equipment_id: str, comment_id: str, *, text: str, actor: CurrentUser
) -> CommentOut:
    await assert_equipment_allowed(session, actor, equipment_id)
    item = await _get_comment(session, equipment_id, comment_id)
    if item.author_user_id != actor.id and actor.role != Role.ADMIN:
        raise DomainError("Você só pode editar os próprios comentários.")
    item.text = text.strip()
    await session.flush()
    await session.commit()
    return _out(item)


async def delete_comment(
    session: AsyncSession, equipment_id: str, comment_id: str, actor: CurrentUser
) -> None:
    await assert_equipment_allowed(session, actor, equipment_id)
    item = await _get_comment(session, equipment_id, comment_id)
    if item.author_user_id != actor.id and actor.role != Role.ADMIN:
        raise DomainError("Você só pode excluir os próprios comentários.")
    await session.delete(item)
    await session.commit()
