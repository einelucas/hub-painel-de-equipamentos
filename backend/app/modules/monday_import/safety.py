"""Salvaguarda contra execução acidental do apply em produção.

Espelha a proteção já existente em `alembic/env.py`: só roda quando
`APP_ENV` é `test`/`development`, e interrompe se a URL de conexão tiver
qualquer indício de produção. Não é uma garantia absoluta — é uma última
barreira explícita antes de uma escrita administrativa no domínio.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from app.core.config import Settings

_PRODUCTION_HINTS = ("prod", "production", "prd")


class UnsafeMigrationTargetError(RuntimeError):
    pass


def describe_url_without_secret(url: str) -> str:
    parts = urlsplit(url)
    host = parts.hostname or "?"
    port = parts.port or "?"
    user = parts.username or "?"
    database = parts.path.lstrip("/") or "?"
    return f"host={host} port={port} user={user} database={database}"


def guard_write_target(settings: Settings) -> str:
    """Levanta `UnsafeMigrationTargetError` se o alvo não parecer DEV/TESTE.
    Devolve a descrição do alvo (sem senha) para exibição ao operador."""
    if settings.app_env not in ("test", "development"):
        raise UnsafeMigrationTargetError(
            f"APP_ENV='{settings.app_env}' não é 'test' nem 'development'. "
            "O apply do importador Monday só roda contra banco DEV/TESTE."
        )
    description = describe_url_without_secret(settings.database_url)
    lowered = settings.database_url.lower()
    if any(hint in lowered for hint in _PRODUCTION_HINTS):
        raise UnsafeMigrationTargetError(
            f"A URL de conexão contém indício de produção ({description}). "
            "Apply interrompido por segurança."
        )
    return description
