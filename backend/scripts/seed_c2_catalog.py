"""Seed único e idempotente dos cadastros pendentes do C2 (Unit, ProjectContext,
Areas, Disciplines, Work Packages, Users + acesso de unidade).

Uso: .venv/Scripts/python.exe scripts/seed_c2_catalog.py

Idempotente: reexecutar não duplica registros (lookup por chave natural antes
de criar). Não faz parte do CLI de importação (`app.modules.monday_import`);
é um seed administrativo avulso, pensado para rodar uma vez em DEV.
"""

from __future__ import annotations

import asyncio
import json

from sqlalchemy import select

from app.core.auth import CurrentUser
from app.core.database import SessionLocal
from app.core.permissions import Role
from app.models.access import UserUnitAccess
from app.models.equipment import Area, Discipline, ProjectContext, Unit, WorkPackage
from app.models.user import User
from app.modules.access.service import replace_user_units
from app.modules.users.service import create_user

WORK_PACKAGE_CODES = [
    "AUT001",
    "CAL001",
    "CAL003",
    "CAL004",
    "CAL006",
    "CAL007",
    "CAL008",
    "CAL009",
    "CAL010",
    "CAL011",
    "CAL012",
    "CIV001",
    "CIV002",
    "CIV003",
    "CIV004",
    "CIV005",
    "CIV006",
    "CIV008",
    "CIV012",
    "CIV014",
    "CIV015",
    "EIA001",
    "ELT001",
    "MEC001",
]

AREA_NAMES = ["Caldeira", "Casa de Força", "Drenagem", "Geral", "Pipe Rack"]

DISCIPLINES = [
    ("EI", "E&I"),
    ("METAL_MEC", "Metal Mec."),
    ("AUTOMACAO", "Automação"),
]

# E-mails provisórios: substituir pelos corporativos oficiais quando
# disponíveis (troca de `email` não altera `User.id`, então as relações com
# Equipment.responsible_user_id permanecem intactas).
RESPONSIBLES = [
    ("Ediel", "ediel@inpasa.com.br"),
    ("Uilson", "uilson@inpasa.com.br"),
    ("Ana Carolina", "ana.carolina@inpasa.com.br"),
    ("Samuel", "samuel@inpasa.com.br"),
]


async def main() -> None:
    async with SessionLocal() as session:
        admin = (
            await session.execute(select(User).where(User.role == Role.ADMIN, User.active.is_(True)))
        ).scalars().first()
        if admin is None:
            raise SystemExit("Nenhum usuário ADMIN ativo encontrado para atuar como ator de auditoria")
        actor = CurrentUser(id=admin.id, email=admin.email, name=admin.name, role=Role.ADMIN, active=True)

        # 1. Unit LEM
        unit = (await session.execute(select(Unit).where(Unit.code == "LEM"))).scalar_one_or_none()
        if unit is None:
            unit = Unit(code="LEM", name="Luís Eduardo Magalhães", active=True)
            session.add(unit)
            await session.flush()
        print(f"Unit LEM = {unit.id}")

        # 2. ProjectContext C2
        context = (
            await session.execute(
                select(ProjectContext).where(ProjectContext.unit_id == unit.id, ProjectContext.code == "C2")
            )
        ).scalar_one_or_none()
        if context is None:
            context = ProjectContext(unit_id=unit.id, code="C2", name="Caldeira 2", active=True)
            session.add(context)
            await session.flush()
        print(f"ProjectContext C2 = {context.id}")

        # 3. Areas
        area_ids: dict[str, str] = {}
        for name in AREA_NAMES:
            area = (
                await session.execute(select(Area).where(Area.unit_id == unit.id, Area.name == name))
            ).scalar_one_or_none()
            if area is None:
                area = Area(unit_id=unit.id, name=name, active=True)
                session.add(area)
                await session.flush()
            area_ids[name] = area.id
        print("Areas:", json.dumps(area_ids, ensure_ascii=False, indent=2))

        # 4. Disciplines
        discipline_ids: dict[str, str] = {}
        for code, name in DISCIPLINES:
            discipline = (
                await session.execute(select(Discipline).where(Discipline.code == code))
            ).scalar_one_or_none()
            if discipline is None:
                discipline = Discipline(code=code, name=name, active=True)
                session.add(discipline)
                await session.flush()
            discipline_ids[name] = discipline.id
        print("Disciplines:", json.dumps(discipline_ids, ensure_ascii=False, indent=2))

        # 5. Work Packages
        work_package_ids: dict[str, str] = {}
        for code in WORK_PACKAGE_CODES:
            wp = (
                await session.execute(
                    select(WorkPackage).where(
                        WorkPackage.project_context_id == context.id, WorkPackage.code == code
                    )
                )
            ).scalar_one_or_none()
            if wp is None:
                # Nome provisório = código: a origem Monday não traz um nome de
                # exibição distinto do código do Work Package.
                wp = WorkPackage(project_context_id=context.id, code=code, name=code, active=True)
                session.add(wp)
                await session.flush()
            work_package_ids[code] = wp.id
        print("WorkPackages:", json.dumps(work_package_ids, ensure_ascii=False, indent=2))
        await session.commit()

        # 6. Responsáveis (Users reais, ANALYST, e-mails provisórios)
        responsible_ids: dict[str, str] = {}
        for name, email in RESPONSIBLES:
            user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
            if user is None:
                user = await create_user(session, name=name, email=email, role=Role.ANALYST, admin=actor)
            responsible_ids[name] = user.id

            # 7. Vínculo com Unit LEM (para aparecer no seletor de responsável)
            existing_access = (
                await session.execute(
                    select(UserUnitAccess).where(
                        UserUnitAccess.user_id == user.id, UserUnitAccess.unit_id == unit.id
                    )
                )
            ).scalar_one_or_none()
            if existing_access is None:
                await replace_user_units(session, user_id=user.id, unit_ids=[unit.id], actor=actor)
        print("Responsibles:", json.dumps(responsible_ids, ensure_ascii=False, indent=2))

        summary = {
            "unit_id": unit.id,
            "project_context_id": context.id,
            "areas": area_ids,
            "disciplines": discipline_ids,
            "work_packages": work_package_ids,
            "responsibles": responsible_ids,
        }
        with open("../docs/migration/c2-seed-ids.json", "w", encoding="utf-8") as fh:
            json.dump(summary, fh, ensure_ascii=False, indent=2)
        print("\nResumo salvo em docs/migration/c2-seed-ids.json")


if __name__ == "__main__":
    asyncio.run(main())
