"""Fundação do apply: Work Package N:N, startup do componente e migration run.

Revision ID: 0006_monday_apply_foundation
Revises: 0005_monday_import_foundation
Create Date: 2026-09-20

Motivação: os exports reais do Monday trazem equipamentos com múltiplos
Work Packages (`equipment.work_package_id` era 0..1), e cada subitem tem um
startup próprio, distinto do startup do equipamento pai
(`equipment_component` não tinha essa coluna). `monday_migration_run`
registra qual conjunto de batches + mapping + plano produziu o estado atual
do domínio, para rastreabilidade do apply.

Backfill: `equipment.work_package_id` existente vira uma linha em
`equipment_work_package`. A coluna antiga é preservada (não removida) como
referência "primária" para compatibilidade com consultas/telas atuais.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_monday_apply_foundation"
down_revision: str | None = "0005_monday_import_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    timestamp = postgresql.TIMESTAMP(precision=3)

    op.add_column("equipment_component", sa.Column("startup_at", sa.Date(), nullable=True))

    op.create_table(
        "equipment_work_package",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("equipment_id", sa.String(), nullable=False),
        sa.Column("work_package_id", sa.String(), nullable=False),
        sa.Column("created_at", timestamp, nullable=False),
        sa.ForeignKeyConstraint(["equipment_id"], ["equipment.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["work_package_id"], ["work_package.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "equipment_work_package_pair_key",
        "equipment_work_package",
        ["equipment_id", "work_package_id"],
        unique=True,
    )
    op.create_index(
        "equipment_work_package_equipment_id_idx", "equipment_work_package", ["equipment_id"]
    )

    # Backfill: preserva o vínculo já existente como linha N:N.
    op.execute(
        sa.text(
            """
            INSERT INTO equipment_work_package (id, equipment_id, work_package_id, created_at)
            SELECT gen_random_uuid()::text, e.id, e.work_package_id, NOW()
            FROM equipment e
            WHERE e.work_package_id IS NOT NULL
            """
        )
    )

    op.create_table(
        "monday_migration_run",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("project_context_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("batch_ids", postgresql.JSONB(), nullable=False),
        sa.Column("mapping_sha256", sa.String(length=64), nullable=False),
        sa.Column("plan_sha256", sa.String(length=64), nullable=False),
        sa.Column("actor_id", sa.String(), nullable=False),
        sa.Column("summary", postgresql.JSONB(), nullable=True),
        sa.Column("error", sa.String(length=2000), nullable=True),
        sa.Column("started_at", timestamp, nullable=False),
        sa.Column("completed_at", timestamp, nullable=True),
        sa.CheckConstraint(
            "status IN ('PLANNED', 'APPLYING', 'APPLIED', 'FAILED')",
            name="monday_migration_run_status_check",
        ),
        sa.ForeignKeyConstraint(
            ["project_context_id"], ["project_context.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["actor_id"], ["User.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "monday_migration_run_context_idx", "monday_migration_run", ["project_context_id"]
    )
    op.create_index("monday_migration_run_plan_idx", "monday_migration_run", ["plan_sha256"])


def downgrade() -> None:
    op.drop_index("monday_migration_run_plan_idx", table_name="monday_migration_run")
    op.drop_index("monday_migration_run_context_idx", table_name="monday_migration_run")
    op.drop_table("monday_migration_run")

    op.drop_index(
        "equipment_work_package_equipment_id_idx", table_name="equipment_work_package"
    )
    op.drop_index("equipment_work_package_pair_key", table_name="equipment_work_package")
    op.drop_table("equipment_work_package")

    op.drop_column("equipment_component", "startup_at")
