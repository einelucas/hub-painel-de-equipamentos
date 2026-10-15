"""Seed idempotente de dois usuários de teste (responsáveis na importação).

Uso (a partir de backend/): .venv/Scripts/python.exe scripts/seed_import_test_users.py

Sem senha: a autenticação é via Keycloak (sem coluna de senha em User); o
vínculo ocorre no primeiro login pelo `externalUserId` (aqui nulo).
Pula e-mails já existentes (comparação case-insensitive). Não altera nada além.
"""

from __future__ import annotations

import asyncio

from sqlalchemy import func, select

from app.core.auth import KEYCLOAK_AUTH_PROVIDER
from app.core.database import SessionLocal
from app.core.permissions import Role
from app.models.user import User

USERS = [
    ("Ediel Nascimento", "ediel.nascimento@inpasa.com.br"),
    ("Anderson dos Santos", "anderson.dossantos@inpasa.com.br"),
]


async def main() -> None:
    async with SessionLocal() as session:
        for name, email in USERS:
            existing = (
                await session.execute(select(User).where(func.lower(User.email) == email.lower()))
            ).scalar_one_or_none()
            if existing is not None:
                print(f"existe: {existing.id} {existing.name} {existing.email}")
                continue
            user = User(
                name=name,
                email=email,
                emailVerified=True,
                role=Role.VIEWER,
                active=True,
                authProvider=KEYCLOAK_AUTH_PROVIDER,
                externalUserId=None,
            )
            session.add(user)
            await session.flush()
            print(f"criado: {user.id} {name} {email}")
        await session.commit()

        rows = (
            await session.execute(
                select(User).where(func.lower(User.email).in_([e.lower() for _, e in USERS]))
            )
        ).scalars().all()
        for u in rows:
            print(f"SELECT: id={u.id} nome={u.name} email={u.email} ativo={u.active} papel={u.role.value}")


if __name__ == "__main__":
    asyncio.run(main())
