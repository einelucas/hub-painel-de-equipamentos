"""Autenticação local por e-mail e senha, com credenciais persistidas no banco.

A senha fica em `Account.password` (providerId `credential`) como hash scrypt;
o login cria uma linha em `Session` guardando só o SHA-256 do token opaco
entregue ao cliente — um vazamento do banco não expõe tokens válidos.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import UnauthorizedError
from app.models.common import utcnow
from app.models.user import Account, Role, Session, User

LOCAL_AUTH_PROVIDER = "LOCAL"
CREDENTIAL_PROVIDER_ID = "credential"

_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_INVALID_CREDENTIALS = "E-mail ou senha inválidos"


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P)
    encode = base64.b64encode
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${encode(salt).decode()}${encode(digest).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt_b64, digest_b64 = stored.split("$")
        if scheme != "scrypt":
            return False
        expected = base64.b64decode(digest_b64)
        actual = hashlib.scrypt(
            password.encode(), salt=base64.b64decode(salt_b64), n=int(n), r=int(r), p=int(p)
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


# Hash descartável: mantém o tempo de resposta igual quando o e-mail não existe.
_DUMMY_HASH = hash_password(secrets.token_urlsafe(16))


def _token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def normalize_email(email: str) -> str:
    return email.strip().lower()


async def upsert_local_user(
    session: AsyncSession, *, email: str, password: str, name: str, role: Role
) -> User:
    """Cria ou atualiza (nome, perfil e senha) um usuário com login local."""
    email = normalize_email(email)
    user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is None:
        user = User(
            name=name,
            email=email,
            emailVerified=True,
            role=role,
            active=True,
            authProvider=LOCAL_AUTH_PROVIDER,
        )
        session.add(user)
        await session.flush()
    else:
        user.name = name
        user.role = role
        user.active = True

    account = (
        await session.execute(
            select(Account).where(Account.userId == user.id, Account.providerId == CREDENTIAL_PROVIDER_ID)
        )
    ).scalar_one_or_none()
    if account is None:
        account = Account(userId=user.id, accountId=user.id, providerId=CREDENTIAL_PROVIDER_ID)
        session.add(account)
    account.password = hash_password(password)
    await session.flush()
    return user


async def authenticate(session: AsyncSession, email: str, password: str) -> User:
    row = (
        await session.execute(
            select(User, Account.password)
            .join(Account, Account.userId == User.id)
            .where(
                User.email == normalize_email(email),
                Account.providerId == CREDENTIAL_PROVIDER_ID,
            )
        )
    ).first()
    if row is None:
        verify_password(password, _DUMMY_HASH)
        raise UnauthorizedError(_INVALID_CREDENTIALS)
    user, stored = row
    if not stored or not verify_password(password, stored) or not user.active:
        raise UnauthorizedError(_INVALID_CREDENTIALS)
    return user


async def create_session(
    session: AsyncSession,
    user: User,
    *,
    ttl: timedelta,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> tuple[str, Session]:
    """Abre uma sessão e devolve o token em claro (só existe nesta resposta)."""
    token = secrets.token_urlsafe(32)
    now = utcnow()
    record = Session(
        userId=user.id,
        token=_token_digest(token),
        expiresAt=now + ttl,
        ipAddress=ip_address,
        userAgent=user_agent,
    )
    session.add(record)
    user.lastLoginAt = now
    await session.flush()
    return token, record


async def resolve_session_user(session: AsyncSession, token: str) -> User | None:
    row = (
        await session.execute(
            select(User, Session.expiresAt)
            .join(Session, Session.userId == User.id)
            .where(Session.token == _token_digest(token))
        )
    ).first()
    if row is None:
        return None
    user, expires_at = row
    if expires_at <= utcnow():
        raise UnauthorizedError("Sessão expirada")
    return user


async def revoke_session(session: AsyncSession, token: str) -> None:
    await session.execute(delete(Session).where(Session.token == _token_digest(token)))
