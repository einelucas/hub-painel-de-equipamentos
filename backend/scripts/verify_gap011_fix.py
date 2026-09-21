"""Verificação rápida e direta (sem HTTP) do GAP-011: filtro por
`discipline_id` na fila de Engenharia. Roda contra o banco TEST
(neondb_test), não toca em DEV/C2.
"""

from __future__ import annotations

import asyncio
import os

os.environ["DATABASE_URL"] = (
    "postgresql://neondb_owner:npg_zDEtCQS7s8Yl@"
    "ep-red-field-b48nnf5d-pooler.c-6.us-east-2.aws.neon.tech/neondb_test"
    "?sslmode=require&channel_binding=require"
)
os.environ["APP_ENV"] = "test"

from sqlalchemy import select  # noqa: E402

from app.core.auth import CurrentUser  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.core.permissions import Role  # noqa: E402
from app.models.equipment import Discipline, Equipment, ProjectContext, Unit  # noqa: E402
from app.models.user import User  # noqa: E402
from app.modules.equipments.service import create_equipment  # noqa: E402
from app.modules.queues.service import QueueFilters, engineering_queue  # noqa: E402


async def main() -> None:
    async with SessionLocal() as session:
        admin = (
            await session.execute(select(User).where(User.role == Role.ADMIN, User.active.is_(True)))
        ).scalars().first()
        actor = CurrentUser(id=admin.id, email=admin.email, name=admin.name, role=Role.ADMIN, active=True)

        unit = Unit(code="GAP011", name="Unidade verificação GAP-011", active=True)
        session.add(unit)
        await session.flush()
        context = ProjectContext(unit_id=unit.id, code="GAP011", name="Contexto verificação", active=True)
        session.add(context)
        await session.flush()
        metal_mec = Discipline(code="MM-GAP011", name="Metal Mec.", active=True)
        eletrica = Discipline(code="EI-GAP011", name="E&I", active=True)
        session.add_all([metal_mec, eletrica])
        await session.flush()
        await session.commit()

        metal_equipment = await create_equipment(
            session,
            values={
                "project_context_id": context.id,
                "name": "Equipamento Metal Mec. GAP-011",
                "origin": None,
                "startup_at": None,
                "discipline_id": metal_mec.id,
                "area_id": None,
                "work_package_ids": [],
                "responsible_user_id": None,
                "criticality": None,
                "capex_estimated": None,
            },
            actor=actor,
        )
        await create_equipment(
            session,
            values={
                "project_context_id": context.id,
                "name": "Equipamento E&I GAP-011",
                "origin": None,
                "startup_at": None,
                "discipline_id": eletrica.id,
                "area_id": None,
                "work_package_ids": [],
                "responsible_user_id": None,
                "criticality": None,
                "capex_estimated": None,
            },
            actor=actor,
        )

        unfiltered = await engineering_queue(session, QueueFilters(unit_id=unit.id), actor)
        print("Sem filtro:", [item.equipment_name for item in unfiltered.items])
        assert len(unfiltered.items) == 2

        filtered = await engineering_queue(
            session, QueueFilters(unit_id=unit.id, discipline_id=metal_mec.id), actor
        )
        print("Filtrado por Metal Mec.:", [item.equipment_name for item in filtered.items])
        assert [item.equipment_id for item in filtered.items] == [metal_equipment.id]

        print("\nGAP-011 (filtro backend): CORRIGIDO — discipline_id filtra a fila de engenharia.")


if __name__ == "__main__":
    asyncio.run(main())
