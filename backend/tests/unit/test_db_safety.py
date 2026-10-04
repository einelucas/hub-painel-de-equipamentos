"""Testes da guarda da suíte destrutiva (`tests/db_safety.py`).

Nenhum teste aqui conecta em banco: a política é pura e o teste de bloqueio
real roda o pytest em subprocesso com rede e DNS bloqueados.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.db_safety import UnsafeTestDatabaseError, validate_destructive_test_target

LOCAL_URL = "postgresql://u:p@localhost:5432/painel_equipamentos_test"
FAKE_NEON_URL = "postgresql://x:x@ep-fake.neon.tech/fake_test"


def _env(**overrides: str | None) -> dict[str, str]:
    env = {
        "APP_ENV": "test",
        "ALLOW_DESTRUCTIVE_TESTS": "true",
        "DATABASE_URL": LOCAL_URL,
        "MIGRATION_DATABASE_URL": LOCAL_URL,
    }
    for key, value in overrides.items():
        if value is None:
            env.pop(key, None)
        else:
            env[key] = value
    return env


@pytest.mark.parametrize(
    "url",
    [
        LOCAL_URL,
        "postgresql://u:p@127.0.0.1:55432/x_test",
        "postgresql://u:p@[::1]:5432/x_test",
        "postgresql+asyncpg://u:p@LOCALHOST/x_test",
        "postgresql://u:p@localhost/x_test?sslmode=disable",
    ],
)
def test_accepts_local_test_database(url: str) -> None:
    validate_destructive_test_target(_env(DATABASE_URL=url, MIGRATION_DATABASE_URL=url))


def test_accepts_missing_migration_url() -> None:
    validate_destructive_test_target(_env(MIGRATION_DATABASE_URL=None))


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"DATABASE_URL": FAKE_NEON_URL}, "host não local"),
        ({"DATABASE_URL": "postgresql://u:p@ep-x-pooler.aws.neon.tech/db_test"}, "host não local"),
        ({"DATABASE_URL": "postgresql://u:p@10.0.0.5:5432/x_test"}, "host não local"),
        ({"DATABASE_URL": "postgresql://u:p@203.0.113.7/x_test"}, "host não local"),
        ({"DATABASE_URL": "postgresql://u:p@db.internal/x_test"}, "host não local"),
        ({"DATABASE_URL": "postgresql://u:p@localhost.evil.com/x_test"}, "host não local"),
        ({"DATABASE_URL": "postgresql://u:p@localhost/painel_equipamentos"}, "não termina em"),
        ({"DATABASE_URL": "postgresql://u:p@localhost/neondb"}, "não termina em"),
        ({"APP_ENV": "development"}, "APP_ENV"),
        ({"APP_ENV": "production"}, "APP_ENV"),
        ({"APP_ENV": None}, "APP_ENV"),
        ({"ALLOW_DESTRUCTIVE_TESTS": None}, "ALLOW_DESTRUCTIVE_TESTS"),
        ({"ALLOW_DESTRUCTIVE_TESTS": "false"}, "ALLOW_DESTRUCTIVE_TESTS"),
        ({"ALLOW_DESTRUCTIVE_TESTS": "1"}, "ALLOW_DESTRUCTIVE_TESTS"),
        ({"MIGRATION_DATABASE_URL": FAKE_NEON_URL}, "MIGRATION_DATABASE_URL"),
        ({"MIGRATION_DATABASE_URL": "postgresql://u:p@localhost/prod"}, "MIGRATION_DATABASE_URL"),
        ({"DATABASE_URL": None}, "DATABASE_URL ausente"),
        ({"DATABASE_URL": ""}, "DATABASE_URL ausente"),
        ({"DATABASE_URL": "not a url"}, "inválida"),
        ({"DATABASE_URL": "mysql://u:p@localhost/x_test"}, "inválida"),
        ({"DATABASE_URL": "postgresql://u:p@localhost:notaport/x_test"}, "inválida"),
        ({"DATABASE_URL": "postgresql://u:p@/x_test"}, "host ausente"),
        ({"DATABASE_URL": "postgresql://u:p@localhost/"}, "nome do banco"),
        ({"DATABASE_URL": "postgresql://u:p@localhost,ep-x.neon.tech/x_test"}, "múltiplos hosts"),
        ({"DATABASE_URL": "postgresql://u:p@localhost/x_test?host=ep-x.neon.tech"}, "redirecionam"),
        ({"DATABASE_URL": "postgresql://u:p@localhost/x_test?hostaddr=203.0.113.7"}, "redirecionam"),
        ({"DATABASE_URL": "postgresql://u:p@localhost/x_test?dbname=neondb"}, "redirecionam"),
    ],
)
def test_rejects_unsafe_target(overrides: dict[str, str | None], message: str) -> None:
    with pytest.raises(UnsafeTestDatabaseError, match=message):
        validate_destructive_test_target(_env(**overrides))


def test_unsafe_error_is_runtime_error() -> None:
    assert issubclass(UnsafeTestDatabaseError, RuntimeError)


_BLOCKED_RUNNER = r"""
import json, socket, sys

attempts = []

def _blocked(kind):
    def _raise(*args, **kwargs):
        attempts.append(kind)
        raise OSError(f"network blocked in safety test ({kind})")
    return _raise

socket.socket.connect = _blocked("connect")
socket.socket.connect_ex = _blocked("connect_ex")
socket.getaddrinfo = _blocked("getaddrinfo")
socket.create_connection = _blocked("create_connection")

import pytest

rc = pytest.main(["--collect-only", "-q", "-p", "no:cacheprovider", "tests/unit/test_db_safety.py"])
app_modules = sorted(m for m in sys.modules if m == "app" or m.startswith("app."))
print("RESULT=" + json.dumps({"rc": int(rc), "app_modules": app_modules, "attempts": attempts}))
"""


def test_conftest_aborts_on_fake_neon_url_before_importing_app() -> None:
    backend_dir = Path(__file__).resolve().parents[2]
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYTEST_")}
    env.update(
        APP_ENV="test",
        ALLOW_DESTRUCTIVE_TESTS="true",
        DATABASE_URL=FAKE_NEON_URL,
        MIGRATION_DATABASE_URL=FAKE_NEON_URL,
    )

    proc = subprocess.run(
        [sys.executable, "-c", _BLOCKED_RUNNER],
        cwd=backend_dir,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        check=False,
    )
    output = proc.stdout + proc.stderr
    result_line = next(line for line in proc.stdout.splitlines() if line.startswith("RESULT="))
    result = json.loads(result_line.removeprefix("RESULT="))

    assert result["rc"] != 0, output
    assert "UnsafeTestDatabaseError" in output, output
    assert "ep-fake.neon.tech" in output, output
    assert result["app_modules"] == [], output
    assert result["attempts"] == [], output
