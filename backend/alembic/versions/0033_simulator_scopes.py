"""Separar cadastros do Simulador do domínio operacional, preservando cenários.

Revision ID: 0033_simulator_scopes
Revises: 0032_startup_simulation
"""
from __future__ import annotations

import unicodedata
import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import TIMESTAMP

revision = "0033_simulator_scopes"
down_revision = "0032_startup_simulation"
branch_labels = None
depends_on = None


def _key(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return " ".join(
        "".join(char for char in normalized if not unicodedata.combining(char)).casefold().split()
    )


def _unique_name(value: str, code: str | None, used: set[str]) -> tuple[str, str]:
    name = " ".join((value or "").split())[:160] or "Sem identificação"
    original = name
    suffix = code or ""
    count = 1
    while _key(name) in used:
        tag = suffix or str(count)
        tail = f" ({tag})"
        name = original[:160 - len(tail)] + tail
        count += 1
        if count > 1:
            suffix = str(count)
    used.add(_key(name))
    return name, _key(name)


def upgrade() -> None:
    op.create_table(
        "startup_simulation_unit",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("name_key", sa.String(160), nullable=False, unique=True),
        sa.Column("created_at", TIMESTAMP(precision=3, timezone=False), nullable=False),
    )
    op.create_table(
        "startup_simulation_project",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("unit_id", sa.String(),
                  sa.ForeignKey("startup_simulation_unit.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("name_key", sa.String(160), nullable=False),
        # Referência histórica sem FK operacional. Usada só para downgrade seguro.
        sa.Column("legacy_project_context_id", sa.String(), nullable=True),
        sa.Column("created_at", TIMESTAMP(precision=3, timezone=False), nullable=False),
    )
    op.create_index(
        "startup_simulation_project_unit_name_key", "startup_simulation_project",
        ["unit_id", "name_key"], unique=True,
    )
    op.add_column("startup_scenario", sa.Column("simulation_project_id", sa.String(), nullable=True))

    conn = op.get_bind()
    rows = conn.execute(sa.text("""
        SELECT DISTINCT pc.id AS project_id, pc.name AS project_name, pc.code AS project_code,
               u.id AS unit_id, u.name AS unit_name, u.code AS unit_code
        FROM startup_scenario AS scenario
        JOIN project_context AS pc ON pc.id = scenario.project_context_id
        JOIN unit AS u ON u.id = pc.unit_id
        ORDER BY u.id, pc.id
    """)).mappings().all()
    units: dict[str, str] = {}
    project_keys: dict[str, set[str]] = {}
    used_unit_keys: set[str] = set()
    now = datetime.now(UTC).replace(tzinfo=None)
    for row in rows:
        old_unit = str(row["unit_id"])
        if old_unit not in units:
            name, name_key = _unique_name(
                row["unit_name"], row["unit_code"], used_unit_keys
            )
            new_unit_id = str(uuid.uuid4())
            conn.execute(sa.text("""
                INSERT INTO startup_simulation_unit (id, name, name_key, created_at)
                VALUES (:id, :name, :name_key, :created_at)
            """), {
                "id": new_unit_id, "name": name, "name_key": name_key, "created_at": now,
            })
            units[old_unit] = new_unit_id
            project_keys[new_unit_id] = set()
        unit_id = units[old_unit]
        name, name_key = _unique_name(
            row["project_name"], row["project_code"], project_keys[unit_id]
        )
        project_id = str(uuid.uuid4())
        conn.execute(sa.text("""
            INSERT INTO startup_simulation_project
            (id, unit_id, name, name_key, legacy_project_context_id, created_at)
            VALUES (:id, :unit_id, :name, :name_key, :legacy_id, :created_at)
        """), {
            "id": project_id, "unit_id": unit_id, "name": name,
            "name_key": name_key, "legacy_id": row["project_id"], "created_at": now,
        })
        conn.execute(sa.text("""
            UPDATE startup_scenario SET simulation_project_id = :new_id
            WHERE project_context_id = :old_id
        """), {"new_id": project_id, "old_id": row["project_id"]})

    op.alter_column("startup_scenario", "simulation_project_id", nullable=False)
    op.create_foreign_key(
        "startup_scenario_simulation_project_id_fkey", "startup_scenario",
        "startup_simulation_project", ["simulation_project_id"], ["id"], ondelete="RESTRICT",
    )
    op.drop_index("startup_scenario_context_created_idx", table_name="startup_scenario")
    op.drop_constraint(
        "startup_scenario_project_context_id_fkey", "startup_scenario", type_="foreignkey"
    )
    op.drop_column("startup_scenario", "project_context_id")
    op.create_index(
        "startup_scenario_context_created_idx", "startup_scenario",
        ["simulation_project_id", "created_at"],
    )


def downgrade() -> None:
    conn = op.get_bind()
    # Não descartar cenários novos do simulador silenciosamente em um rollback.
    unmatched = conn.execute(sa.text("""
        SELECT COUNT(*) FROM startup_scenario AS s
        JOIN startup_simulation_project AS p ON p.id = s.simulation_project_id
        WHERE p.legacy_project_context_id IS NULL
    """)).scalar_one()
    if unmatched:
        raise RuntimeError(
            "Rollback bloqueado: existem cenários exclusivos do simulador. "
            "Exporte os dados e migre-os explicitamente antes de reverter."
        )
    op.add_column("startup_scenario", sa.Column("project_context_id", sa.String(), nullable=True))
    conn.execute(sa.text("""
        UPDATE startup_scenario AS s SET project_context_id = p.legacy_project_context_id
        FROM startup_simulation_project AS p WHERE p.id = s.simulation_project_id
    """))
    op.alter_column("startup_scenario", "project_context_id", nullable=False)
    op.create_foreign_key(
        "startup_scenario_project_context_id_fkey", "startup_scenario",
        "project_context", ["project_context_id"], ["id"], ondelete="CASCADE",
    )
    op.drop_index("startup_scenario_context_created_idx", table_name="startup_scenario")
    op.drop_constraint(
        "startup_scenario_simulation_project_id_fkey", "startup_scenario", type_="foreignkey"
    )
    op.drop_column("startup_scenario", "simulation_project_id")
    op.create_index(
        "startup_scenario_context_created_idx", "startup_scenario",
        ["project_context_id", "created_at"],
    )
    op.drop_index(
        "startup_simulation_project_unit_name_key", table_name="startup_simulation_project"
    )
    op.drop_table("startup_simulation_project")
    op.drop_table("startup_simulation_unit")
