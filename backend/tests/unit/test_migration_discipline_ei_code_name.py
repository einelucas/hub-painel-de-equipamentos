"""A migration 0019 é set-based, idempotente e trata colisão de code (estático; sem banco)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

PATH = Path(__file__).resolve().parents[2] / "alembic" / "versions" / "0019_discipline_ei_code_name.py"


def _load():
    spec = importlib.util.spec_from_file_location("mig0019", PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(fn: str) -> str:
    module = _load()
    statements: list[str] = []
    module.op.execute = statements.append  # type: ignore[assignment]
    getattr(module, fn)()
    return "\n".join(statements)


def test_revision_chain() -> None:
    module = _load()
    assert module.down_revision == "0018_unify_discipline_ei"
    assert module.revision == "0019_discipline_ei_code_name"
    assert len(module.revision) <= 32


def test_upgrade_is_idempotent_and_collision_safe() -> None:
    sql = _run("upgrade")
    assert "WHERE NOT EXISTS (SELECT 1 FROM discipline WHERE code = 'E&I')" in sql
    assert "Elétrica e Instrumentação" in sql
    assert "UPDATE equipment" in sql  # reatribui na colisão
    assert "active = false" in sql  # desativa legadas
    assert "DELETE" not in sql.upper()


def test_downgrade_guards_unique_code() -> None:
    sql = _run("downgrade")
    assert "NOT EXISTS (SELECT 1 FROM discipline WHERE code = 'EI')" in sql
    assert "DELETE" not in sql.upper()
