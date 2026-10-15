"""Seed idempotente dos administradores com senha padrão (primeiro acesso).

Uso (a partir de backend/): .venv/Scripts/python.exe scripts/seed_default_password_users.py

Cria os usuários como ADMIN ativos com a senha padrão INP@2026; no primeiro login
o sistema exige a definição de uma nova senha. Se o usuário já existe, apenas
garante nome, perfil ADMIN e ativo; a senha só é definida quando ainda não há
credencial — nunca sobrescreve uma senha já trocada.
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.local_auth import (
    CREDENTIAL_PROVIDER_ID,
    DEFAULT_PASSWORD,
    LOCAL_AUTH_PROVIDER,
    hash_password,
    normalize_email,
)
from app.models.user import Account, Role, User

USERS = [
    ("Lucas Pinheiro", "lucas.pinheiro@inpasa.com.br"),
    ("Diego Costa", "diego.costa@inpasa.com.br"),
]


async def seed(session) -> list[str]:
    log: list[str] = []
    for name, raw_email in USERS:
        email = normalize_email(raw_email)
        user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if user is None:
            user = User(
                name=name,
                email=email,
                emailVerified=True,
                role=Role.ADMIN,
                active=True,
                authProvider=LOCAL_AUTH_PROVIDER,
            )
            session.add(user)
            await session.flush()
            log.append(f"criado: {email}")
        else:
            user.role = Role.ADMIN
            user.active = True
            log.append(f"atualizado (perfil/ativo): {email}")
        account = (
            await session.execute(
                select(Account).where(Account.userId == user.id, Account.providerId == CREDENTIAL_PROVIDER_ID)
            )
        ).scalar_one_or_none()
        if account is None:
            session.add(
                Account(
                    userId=user.id,
                    accountId=user.id,
                    providerId=CREDENTIAL_PROVIDER_ID,
                    password=hash_password(DEFAULT_PASSWORD),
                )
            )
            log.append(f"  senha padrão definida: {email}")
        elif not account.password:
            account.password = hash_password(DEFAULT_PASSWORD)
            log.append(f"  senha padrão definida: {email}")
        else:
            log.append(f"  senha existente preservada: {email}")
    await session.flush()
    return log


async def main() -> None:
    async with SessionLocal() as session:
        for line in await seed(session):
            print(line)
        await session.commit()


if __name__ == "__main__":
    asyncio.run(main())
