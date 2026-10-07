"""CLI para cadastrar (ou redefinir) usuários com login local por e-mail e senha.

Uso:
    python -m app.modules.local_auth create-user --email admin@inpasa.com.br \
        --name Administrador --role ADMIN

A senha é lida de LOCAL_AUTH_PASSWORD ou pedida no terminal — nunca por
argumento, para não ficar no histórico do shell.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import os
import sys
from collections.abc import Sequence

from app.models.user import Role


def _read_password() -> str:
    password = os.environ.get("LOCAL_AUTH_PASSWORD")
    if password:
        return password
    password = getpass.getpass("Senha: ")
    if password != getpass.getpass("Confirme a senha: "):
        raise SystemExit("As senhas não conferem; nada foi gravado.")
    return password


async def _create_user(args: argparse.Namespace, password: str) -> None:
    from sqlalchemy import text

    from app.core.database import SessionLocal
    from app.core.local_auth import upsert_local_user

    async with SessionLocal() as session:
        database = (await session.execute(text("SELECT current_database()"))).scalar_one()
        user = await upsert_local_user(
            session, email=args.email, password=password, name=args.name, role=Role(args.role)
        )
        await session.commit()
    print(f"[local_auth] banco={database} usuário={user.email} perfil={user.role.value} id={user.id}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.modules.local_auth")
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create-user", help="Cria ou redefine a senha de um usuário local.")
    create.add_argument("--email", required=True)
    create.add_argument("--name", required=True)
    create.add_argument("--role", choices=[role.value for role in Role], default=Role.VIEWER.value)
    args = parser.parse_args(argv)

    password = _read_password()
    if len(password) < 8:
        print("A senha deve ter pelo menos 8 caracteres; nada foi gravado.", file=sys.stderr)
        return 1
    asyncio.run(_create_user(args, password))
    return 0
