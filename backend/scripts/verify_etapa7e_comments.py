"""Verificação rápida e direta (sem HTTP) da Etapa 7E: comentários do
equipamento. Roda contra o banco TEST (neondb_test), não toca em DEV/C2.
"""

from __future__ import annotations

import asyncio
import os
import uuid

os.environ["DATABASE_URL"] = (
    "postgresql://neondb_owner:npg_zDEtCQS7s8Yl@"
    "ep-red-field-b48nnf5d-pooler.c-6.us-east-2.aws.neon.tech/neondb_test"
    "?sslmode=require&channel_binding=require"
)
os.environ["APP_ENV"] = "test"

from sqlalchemy import select  # noqa: E402

from app.core.auth import CurrentUser  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.core.errors import DomainError  # noqa: E402
from app.core.permissions import Role  # noqa: E402
from app.models.access import UserUnitAccess  # noqa: E402
from app.models.equipment import Discipline, ProjectContext, Unit  # noqa: E402
from app.models.user import User  # noqa: E402
from app.modules.comments import service as comments_service  # noqa: E402
from app.modules.equipments.service import create_equipment  # noqa: E402


async def expect_error(coro, *exc_types) -> None:
    try:
        await coro
    except exc_types:
        return
    raise AssertionError(f"Esperava um erro de {exc_types}, mas não ocorreu")


async def main() -> None:
    async with SessionLocal() as session:
        admin = (
            await session.execute(select(User).where(User.role == Role.ADMIN, User.active.is_(True)))
        ).scalars().first()
        analyst = (
            await session.execute(select(User).where(User.role == Role.ANALYST, User.active.is_(True)))
        ).scalars().first()
        admin_actor = CurrentUser(
            id=admin.id, email=admin.email, name=admin.name, role=Role.ADMIN, active=True
        )
        analyst_actor = CurrentUser(
            id=analyst.id, email=analyst.email, name=analyst.name, role=Role.ANALYST, active=True
        )

        suffix = uuid.uuid4().hex[:6].upper()
        unit = Unit(code=f"ETP7E{suffix}", name="Unidade verificação 7E", active=True)
        session.add(unit)
        await session.flush()
        context = ProjectContext(unit_id=unit.id, code=f"ETP7E{suffix}", name="Contexto verificação 7E", active=True)
        session.add(context)
        await session.flush()
        discipline = Discipline(code=f"MM-ETP7E{suffix}", name="Metal Mec. 7E", active=True)
        session.add(discipline)
        session.add(UserUnitAccess(user_id=analyst.id, unit_id=unit.id))
        await session.flush()
        await session.commit()

        equipment = await create_equipment(
            session,
            values={
                "project_context_id": context.id,
                "name": "Equipamento verificação 7E",
                "origin": None,
                "startup_at": None,
                "discipline_id": discipline.id,
                "area_id": None,
                "work_package_ids": [],
                "responsible_user_id": None,
                "criticality": None,
                "capex_estimated": None,
            },
            actor=admin_actor,
        )
        equipment_id = equipment.id

        empty = await comments_service.list_comments(session, equipment_id, admin_actor)
        assert empty.items == []
        print("OK: lista vazia inicialmente")

        created = await comments_service.create_comment(
            session, equipment_id, text="Primeiro comentário", actor=admin_actor
        )
        assert created.text == "Primeiro comentário"
        assert created.author is not None and created.author.id == admin.id
        assert abs((created.updated_at - created.created_at).total_seconds()) < 1
        print("OK: comentário criado com autor e timestamp corretos")

        listed = await comments_service.list_comments(session, equipment_id, admin_actor)
        assert len(listed.items) == 1
        print("OK: comentário aparece na listagem")

        await expect_error(
            comments_service.update_comment(
                session, equipment_id, created.id, text="Editado por outro", actor=analyst_actor
            ),
            DomainError,
        )
        print("OK: outro usuário não pode editar comentário alheio")

        updated = await comments_service.update_comment(
            session, equipment_id, created.id, text="Editado pelo autor", actor=admin_actor
        )
        assert updated.text == "Editado pelo autor"
        print("OK: autor pode editar o próprio comentário")

        await comments_service.delete_comment(session, equipment_id, created.id, admin_actor)
        after_delete = await comments_service.list_comments(session, equipment_id, admin_actor)
        assert after_delete.items == []
        print("OK: exclusão remove o comentário da listagem")

        print("\nTodas as verificações da Etapa 7E passaram.")


if __name__ == "__main__":
    asyncio.run(main())
