"""Guarda de segurança da suíte de integração destrutiva.

A suíte trunca todas as tabelas após cada teste de integração. Este módulo
decide, ANTES de qualquer import de `app` (que cria engine/session), se o
destino configurado no ambiente pode ser destruído. É puro: não importa
`app`, não abre conexão e não resolve DNS — só lê variáveis e parseia URLs.

Política (todas obrigatórias):
- `APP_ENV=test`;
- `ALLOW_DESTRUCTIVE_TESTS=true` (opt-in explícito);
- `DATABASE_URL` PostgreSQL válida, host estritamente local
  (`localhost`, `127.0.0.1`, `::1`) e banco terminando em `_test`;
- `MIGRATION_DATABASE_URL`, quando presente, sob a mesma política.

Banco remoto (Neon, DEV, produção, qualquer IP/host não local) é sempre
recusado, mesmo que o nome termine em `_test`.
"""

from __future__ import annotations

from collections.abc import Mapping
from urllib.parse import parse_qsl, urlsplit

LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
TEST_DATABASE_SUFFIX = "_test"
OPT_IN_VAR = "ALLOW_DESTRUCTIVE_TESTS"

# Parâmetros libpq que redirecionam host/banco por fora da parte principal
# da URL (`postgresql://localhost/x_test?host=remoto`). Recusados para que a
# validação do host/banco não possa ser contornada.
_REDIRECTING_QUERY_PARAMS = frozenset({"host", "hostaddr", "dbname", "service", "port"})
_ALLOWED_SCHEMES = frozenset({"postgresql", "postgres", "postgresql+asyncpg", "postgresql+psycopg"})


class UnsafeTestDatabaseError(RuntimeError):
    """Destino recusado para a suíte destrutiva."""


def _validate_url(var: str, url: str) -> None:
    try:
        parts = urlsplit(url)
        _ = parts.port  # valida a porta (ValueError se inválida)
    except ValueError as exc:
        raise UnsafeTestDatabaseError(f"{var} inválida: {exc}.") from exc

    if parts.scheme not in _ALLOWED_SCHEMES:
        raise UnsafeTestDatabaseError(
            f"{var} inválida: esquema '{parts.scheme}' não é PostgreSQL."
        )
    if "," in parts.netloc:
        raise UnsafeTestDatabaseError(f"{var} inválida: múltiplos hosts não são permitidos.")

    host = (parts.hostname or "").lower()
    if not host:
        raise UnsafeTestDatabaseError(f"{var} inválida: host ausente.")
    if host not in LOCAL_HOSTS:
        raise UnsafeTestDatabaseError(
            f"{var} aponta para host não local '{host}'. A suíte destrutiva só "
            f"roda contra {sorted(LOCAL_HOSTS)} — nunca Neon, DEV, produção ou "
            "qualquer PostgreSQL remoto."
        )

    redirecting = sorted(
        {key.lower() for key, _ in parse_qsl(parts.query, keep_blank_values=True)}
        & _REDIRECTING_QUERY_PARAMS
    )
    if redirecting:
        raise UnsafeTestDatabaseError(
            f"{var} contém parâmetros que redirecionam a conexão: {redirecting}."
        )

    database = parts.path.lstrip("/")
    if not database or "/" in database:
        raise UnsafeTestDatabaseError(f"{var} inválida: nome do banco ausente ou malformado.")
    if not database.endswith(TEST_DATABASE_SUFFIX):
        raise UnsafeTestDatabaseError(
            f"{var} aponta para o banco '{database}', que não termina em "
            f"'{TEST_DATABASE_SUFFIX}'."
        )


def validate_destructive_test_target(env: Mapping[str, str]) -> None:
    """Levanta `UnsafeTestDatabaseError` se `env` não autoriza a suíte destrutiva."""
    app_env = env.get("APP_ENV", "")
    if app_env != "test":
        raise UnsafeTestDatabaseError(f"APP_ENV='{app_env}' (esperado 'test').")

    opt_in = env.get(OPT_IN_VAR, "").strip().lower()
    if opt_in != "true":
        raise UnsafeTestDatabaseError(
            f"{OPT_IN_VAR} não está habilitado (valor: '{env.get(OPT_IN_VAR, '')}'). "
            f"Defina {OPT_IN_VAR}=true apenas em um ambiente local descartável."
        )

    database_url = env.get("DATABASE_URL", "").strip()
    if not database_url:
        raise UnsafeTestDatabaseError("DATABASE_URL ausente.")
    _validate_url("DATABASE_URL", database_url)

    migration_url = env.get("MIGRATION_DATABASE_URL", "").strip()
    if migration_url:
        _validate_url("MIGRATION_DATABASE_URL", migration_url)
