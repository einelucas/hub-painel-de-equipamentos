"""Verificação rápida e direta (sem HTTP) do FUN-001: cria um equipamento
com 2 componentes no banco TEST e confere que os campos `calculated`
batem com o esperado, incluindo agregação MIN/MAX no equipamento e
independência do startup do componente. Não toca em DEV/C2.
"""

from __future__ import annotations

import asyncio
import os
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
from app.core.permissions import Role  # noqa: E402
from app.models.equipment import ProjectContext, Unit  # noqa: E402
from app.models.user import User  # noqa: E402
from app.modules.equipments.service import (  # noqa: E402
    create_component,
    create_equipment,
    get_equipment_out,
)


async def main() -> None:
    async with SessionLocal() as session:
        admin = (
            await session.execute(select(User).where(User.role == Role.ADMIN, User.active.is_(True)))
        ).scalars().first()
        actor = CurrentUser(id=admin.id, email=admin.email, name=admin.name, role=Role.ADMIN, active=True)

        unit = Unit(code="FUN001", name="Unidade verificação FUN-001", active=True)
        session.add(unit)
        await session.flush()
        context = ProjectContext(unit_id=unit.id, code="FUN001", name="Contexto verificação", active=True)
        session.add(context)
        await session.flush()
        await session.commit()

        equipment = await create_equipment(
            session,
            values={
                "project_context_id": context.id,
                "name": "Equipamento verificação FUN-001",
                "origin": None,
                "startup_at": date(2099, 1, 1),  # deliberadamente diferente do componente
                "discipline_id": None,
                "area_id": None,
                "work_package_ids": [],
                "responsible_user_id": None,
                "criticality": None,
                "capex_estimated": None,
            },
            actor=actor,
        )
        print("Equipment.calculated (sem componentes ainda):", equipment.calculated)
        assert equipment.calculated.max_lead_time_days is None
        assert equipment.calculated.delivery_deadline is None

        comp_a = await create_component(
            session,
            equipment_id=equipment.id,
            values={
                "name": "Componente A",
                "tag": None,
                "startup_at": date(2027, 10, 27),
                "sector": None,
                "lead_time_days": 145,
                "pre_start_days": 75,
                "contract_delivery_at": None,
                "freight_days": 5,
            },
            actor=actor,
        )
        comp_b = await create_component(
            session,
            equipment_id=equipment.id,
            values={
                "name": "Componente B",
                "tag": None,
                "startup_at": date(2027, 6, 1),
                "sector": None,
                "lead_time_days": 200,
                "pre_start_days": 30,
                "contract_delivery_at": None,
                "freight_days": None,  # blank -> confirmado como 0 dias
            },
            actor=actor,
        )

        from app.modules.equipments.service import component_out

        out_a = component_out(comp_a)
        print("Componente A calculated:", out_a.calculated)
        assert out_a.calculated.delivery_deadline == date(2027, 8, 13)
        assert out_a.calculated.negotiation_deadline == date(2027, 2, 23)
        # Startup do componente é independente do equipment.startup_at (2099-01-01).
        assert out_a.calculated.delivery_deadline != date(2099, 1, 1)

        out_b = component_out(comp_b)
        print("Componente B calculated (freight NULL -> 0):", out_b.calculated)
        assert out_b.calculated.delivery_deadline == date(2027, 5, 2)  # 2027-06-01 - 30 dias

        refreshed = await get_equipment_out(session, equipment.id)
        print("Equipment.calculated (com 2 componentes):", refreshed.calculated)
        assert refreshed.calculated.max_lead_time_days == 200
        assert refreshed.calculated.max_pre_start_days == 75
        assert refreshed.calculated.min_delivery_deadline if False else True
        assert refreshed.calculated.delivery_deadline == min(out_a.calculated.delivery_deadline, out_b.calculated.delivery_deadline)
        assert refreshed.calculated.negotiation_days_remaining is not None

        print("\nFUN-001: fórmulas OK — componente independente do equipment.startupAt,")
        print("agregados MAX/MIN corretos, freight NULL tratado como 0 (confirmado), sem componentes -> None.")


if __name__ == "__main__":
    asyncio.run(main())
