"""Verifica empiricamente o que o endpoint /history devolve para um
equipamento importado com sub-processos (Negotiation/LegalProcess/Contract/
PurchaseRequest/PurchaseOrder) criados via migration.import. Somente leitura.
"""

from __future__ import annotations

import asyncio

from app.core.auth import CurrentUser
from app.core.database import SessionLocal
from app.core.permissions import Role
from app.models.equipment import Equipment
from app.modules.workflow.service import history
from sqlalchemy import select


async def main() -> None:
    async with SessionLocal() as s:
        eq = (
            await s.execute(
                select(Equipment).where(Equipment.name.ilike("%Biomassa%"), Equipment.current_stage == 8)
            )
        ).scalars().first()
        actor = CurrentUser(id="x", email="x@x.com", name="x", role=Role.ADMIN, active=True)
        result = await history(s, eq.id, actor)
        print("equipment:", eq.name, eq.id)
        print("total entries:", len(result.items))
        for item in result.items:
            print(" -", item.kind, item.action, item.title, item.occurred_at)


if __name__ == "__main__":
    asyncio.run(main())
