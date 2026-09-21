"""Verificação rápida e direta (sem HTTP/pytest) do GAP-001: chama os
serviços diretamente contra o banco TEST (neondb_test) para confirmar que a
resposta da própria chamada de update já reflete os vínculos N:N corretos,
sem depender da lentidão da suíte de integração completa.

Roda com as env vars do TEST apontadas explicitamente (não usa .env real).
Não toca no banco DEV/C2.
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
from app.models.equipment import Area, Discipline, ProjectContext, Unit, WorkPackage  # noqa: E402
from app.models.user import User  # noqa: E402
from app.modules.equipments.service import create_equipment, update_equipment  # noqa: E402


async def main() -> None:
    async with SessionLocal() as session:
        admin = (
            await session.execute(select(User).where(User.role == Role.ADMIN, User.active.is_(True)))
        ).scalars().first()
        if admin is None:
            admin = User(name="Admin verificação", email="verify-gap001@example.com", role=Role.ADMIN, active=True)
            session.add(admin)
            await session.flush()
        actor = CurrentUser(id=admin.id, email=admin.email, name=admin.name, role=Role.ADMIN, active=True)

        unit = Unit(code="GAP001", name="Unidade verificação GAP-001", active=True)
        session.add(unit)
        await session.flush()
        context = ProjectContext(unit_id=unit.id, code="GAP001", name="Contexto verificação", active=True)
        session.add(context)
        await session.flush()

        wp_a = WorkPackage(project_context_id=context.id, code="WP-A", name="A", active=True)
        wp_b = WorkPackage(project_context_id=context.id, code="WP-B", name="B", active=True)
        wp_c = WorkPackage(project_context_id=context.id, code="WP-C", name="C", active=True)
        session.add_all([wp_a, wp_b, wp_c])
        await session.flush()
        await session.commit()

        created = await create_equipment(
            session,
            values={
                "project_context_id": context.id,
                "name": "Equipamento verificação GAP-001",
                "origin": None,
                "startup_at": None,
                "discipline_id": None,
                "area_id": None,
                "work_package_ids": [wp_a.id, wp_b.id],
                "responsible_user_id": None,
                "criticality": None,
                "capex_estimated": None,
            },
            actor=actor,
        )
        print("CREATE workPackages:", sorted(item.id for item in created.work_packages))
        assert sorted(item.id for item in created.work_packages) == sorted([wp_a.id, wp_b.id])

        updated = await update_equipment(
            session,
            equipment_id=created.id,
            changes={"work_package_ids": [wp_b.id, wp_c.id]},
            actor=actor,
        )
        returned_ids = sorted(item.id for item in updated.work_packages)
        print("PATCH response workPackages (deveria ser [B, C]):", returned_ids)
        expected = sorted([wp_b.id, wp_c.id])
        assert returned_ids == expected, f"GAP-001 AINDA PRESENTE: esperado {expected}, veio {returned_ids}"

        # Confirma também numa sessão nova (equivalente a um GET separado).
        async with SessionLocal() as fresh_session:
            from app.modules.equipments.service import get_equipment_out

            fresh = await get_equipment_out(fresh_session, created.id)
            fresh_ids = sorted(item.id for item in fresh.work_packages)
            print("GET (sessão nova) workPackages:", fresh_ids)
            assert fresh_ids == expected

        print("\nGAP-001: CORRIGIDO — resposta do próprio update já reflete [B, C].")
        print("(dados de verificação deixados no banco TEST descartável, sem limpeza necessária)")


if __name__ == "__main__":
    asyncio.run(main())
