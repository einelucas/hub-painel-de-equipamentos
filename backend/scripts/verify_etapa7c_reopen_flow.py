"""Verificação rápida e direta (sem HTTP) da Etapa 7C: reabertura com
aprovação. Roda contra o banco TEST (neondb_test), não toca em DEV/C2.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import date

os.environ["DATABASE_URL"] = (
    "postgresql://neondb_owner:npg_zDEtCQS7s8Yl@"
    "ep-red-field-b48nnf5d-pooler.c-6.us-east-2.aws.neon.tech/neondb_test"
    "?sslmode=require&channel_binding=require"
)
os.environ["APP_ENV"] = "test"

from sqlalchemy import select  # noqa: E402

from app.core.auth import CurrentUser  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.core.errors import ConflictError, DomainError  # noqa: E402
from app.core.permissions import ForbiddenError, Role  # noqa: E402
from app.models.access import UserUnitAccess  # noqa: E402
from app.models.equipment import Discipline, Equipment, ProjectContext, Unit  # noqa: E402
from app.models.process import Negotiation  # noqa: E402
from app.models.user import User  # noqa: E402
from app.modules.equipments.service import create_equipment  # noqa: E402
from app.modules.processes.service import ensure_process, update_process  # noqa: E402
from app.modules.workflow import reopen as reopen_service  # noqa: E402
from app.modules.workflow.service import execute_transition  # noqa: E402


async def expect_error(coro, *exc_types) -> None:
    try:
        await coro
    except exc_types:
        return
    raise AssertionError(f"Esperava um erro de {exc_types}, mas não ocorreu")


async def main() -> None:
    async with SessionLocal() as session:
        admin = (
            (await session.execute(select(User).where(User.role == Role.ADMIN, User.active.is_(True))))
            .scalars()
            .first()
        )
        analyst = (
            (await session.execute(select(User).where(User.role == Role.ANALYST, User.active.is_(True))))
            .scalars()
            .first()
        )
        admin_actor = CurrentUser(
            id=admin.id, email=admin.email, name=admin.name, role=Role.ADMIN, active=True
        )
        analyst_actor = CurrentUser(
            id=analyst.id, email=analyst.email, name=analyst.name, role=Role.ANALYST, active=True
        )

        suffix = uuid.uuid4().hex[:6].upper()
        unit = Unit(code=f"ETP7C{suffix}", name="Unidade verificação 7C", active=True)
        session.add(unit)
        await session.flush()
        context = ProjectContext(
            unit_id=unit.id, code=f"ETP7C{suffix}", name="Contexto verificação 7C", active=True
        )
        session.add(context)
        await session.flush()
        discipline = Discipline(code=f"MM-ETP7C{suffix}", name="Metal Mec. 7C", active=True)
        session.add(discipline)
        session.add(UserUnitAccess(user_id=analyst.id, unit_id=unit.id))
        await session.flush()
        await session.commit()

        equipment = await create_equipment(
            session,
            values={
                "project_context_id": context.id,
                "name": "Equipamento verificação 7C",
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

        await ensure_process(session, Negotiation, equipment_id)
        await update_process(
            session,
            model=Negotiation,
            entity_name="Negotiation",
            equipment_id=equipment_id,
            changes={"equalized": True},
            actor=admin_actor,
        )
        await execute_transition(
            session, equipment_id=equipment_id, target_stage=1, reason=None, actor=admin_actor
        )
        await update_process(
            session,
            model=Negotiation,
            entity_name="Negotiation",
            equipment_id=equipment_id,
            changes={"negotiated_at": date(2026, 1, 1)},
            actor=admin_actor,
        )
        await execute_transition(
            session, equipment_id=equipment_id, target_stage=2, reason=None, actor=admin_actor
        )
        row = (await session.execute(select(Equipment).where(Equipment.id == equipment_id))).scalar_one()
        assert row.current_stage == 2
        print("OK: equipamento avançou até a fase 2")

        # Target must be strictly before current stage.
        await expect_error(
            reopen_service.request_reopen(
                session, equipment_id, target_stage=2, justification="igual", actor=analyst_actor
            ),
            DomainError,
        )
        print("OK: reabertura para a mesma fase é rejeitada")

        request = await reopen_service.request_reopen(
            session,
            equipment_id,
            target_stage=0,
            justification="Necessário revisar negociação",
            actor=analyst_actor,
        )
        assert request.status == "PENDING"
        row = (await session.execute(select(Equipment).where(Equipment.id == equipment_id))).scalar_one()
        assert row.current_stage == 2, "Solicitação não deve mudar a fase"
        print("OK: solicitação criada, fase inalterada enquanto pendente")

        # Second pending request rejected.
        await expect_error(
            reopen_service.request_reopen(
                session, equipment_id, target_stage=1, justification="outra", actor=analyst_actor
            ),
            ConflictError,
        )
        print("OK: segunda solicitação pendente simultânea é rejeitada")

        # Requester cannot approve their own request.
        await expect_error(
            reopen_service.approve_reopen(session, equipment_id, request.id, note=None, actor=analyst_actor),
            ForbiddenError,
            DomainError,
        )
        print("OK: solicitante não pode aprovar a própria solicitação")

        approved = await reopen_service.approve_reopen(
            session, equipment_id, request.id, note="Confirmado", actor=admin_actor
        )
        assert approved.status == "APPROVED"
        row = (await session.execute(select(Equipment).where(Equipment.id == equipment_id))).scalar_one()
        assert row.current_stage == 0, "Aprovação deve mudar para a fase solicitada"
        print("OK: aprovação muda a fase para o destino solicitado (0)")

        # Rejection path: advance again, then create another request and reject it.
        await execute_transition(
            session, equipment_id=equipment_id, target_stage=1, reason=None, actor=admin_actor
        )
        request2 = await reopen_service.request_reopen(
            session, equipment_id, target_stage=0, justification="outra tentativa", actor=analyst_actor
        )
        rejected = await reopen_service.reject_reopen(
            session, equipment_id, request2.id, note="Não procede", actor=admin_actor
        )
        assert rejected.status == "REJECTED"
        row = (await session.execute(select(Equipment).where(Equipment.id == equipment_id))).scalar_one()
        assert row.current_stage == 1, "Rejeição não deve mudar a fase"
        print("OK: rejeição não altera a fase")

        print("\nTodas as verificações da Etapa 7C passaram.")


if __name__ == "__main__":
    asyncio.run(main())
