"""A migration 0018 é set-based e idempotente (verificação estática; sem banco)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

PATH = Path(__file__).resolve().parents[2] / "alembic" / "versions" / "0018_unify_discipline_ei.py"


def _load():
    spec = importlib.util.spec_from_file_location("mig0018", PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_revision_chain_and_statements() -> None:
    module = _load()
    assert module.down_revision == "0017_monday_apply_job"
    statements: list[str] = []
    module.op.execute = statements.append  # type: ignore[assignment]
    module.upgrade()
    sql = "\n".join(statements)
    assert "WHERE NOT EXISTS" in sql  # idempotente
    assert "UPDATE equipment" in sql and "active = false" in sql
    assert "DELETE" not in sql.upper()
    module.downgrade()
