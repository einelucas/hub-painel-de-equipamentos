"""Adiciona cores às disciplinas e catálogo global de criticidades.

Revision ID: 0023_discipline_criticality
Revises: 0022_resilient_apply_jobs
Create Date: 2026-10-16
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0023_discipline_criticality"
down_revision: str | None = "0022_resilient_apply_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("discipline", sa.Column("color", sa.String(length=7), nullable=True))
    op.create_table(
        "criticality_label",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(length=40), nullable=False),
        sa.Column("color", sa.String(length=7), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.add_column("equipment", sa.Column("criticality_label_id", sa.String(), nullable=True))
    op.create_foreign_key(
        "equipment_criticality_label_id_fkey",
        "equipment",
        "criticality_label",
        ["criticality_label_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "equipment_criticality_label_id_idx", "equipment", ["criticality_label_id"]
    )

    discipline_colors = {
        "CIV": "#216edf", "MEC": "#ff8358", "MM": "#ff8358", "E&I": "#b0dc51",
        "EI": "#b0dc51", "ELE": "#b0dc51", "EIA": "#b0dc51", "AUT": "#e8697d",
        "CAL": "#fdbf6b", "PDC": "#b57de3", "OPE": "#17b897", "SUP": "#00a8cc",
        "PRO": "#845ec2", "MAN": "#e17055", "QUA": "#00b894", "LAB": "#0984e3",
        "OUT": "#747d8c",
    }
    for code, color in discipline_colors.items():
        op.execute(
            sa.text("UPDATE discipline SET color = :color WHERE upper(code) = :code")
            .bindparams(color=color, code=code)
        )

    labels = [
        ("Longo > 180", "#6645a9"),
        ("Médio 90~180", "#777ae5"),
        ("Curto < 90", "#79affd"),
    ]
    for name, color in labels:
        op.execute(
            sa.text(
                "INSERT INTO criticality_label (id, name, color, active) "
                "VALUES (gen_random_uuid()::text, :name, :color, true)"
            ).bindparams(name=name, color=color)
        )
    op.execute(
        """
        UPDATE equipment e
        SET criticality_label_id = c.id
        FROM criticality_label c
        WHERE CASE
          WHEN lower(coalesce(e.criticality, '')) LIKE 'longo%' THEN c.name = 'Longo > 180'
          WHEN lower(coalesce(e.criticality, '')) LIKE 'médio%'
            OR lower(coalesce(e.criticality, '')) LIKE 'medio%' THEN c.name = 'Médio 90~180'
          WHEN lower(coalesce(e.criticality, '')) LIKE 'curto%' THEN c.name = 'Curto < 90'
          ELSE false
        END
        """
    )
    # Valores históricos fora das três faixas oficiais também viram etiquetas,
    # com cor neutra. Assim nenhum texto existente é perdido ao editar.
    op.execute(
        """
        INSERT INTO criticality_label (id, name, color, active)
        SELECT gen_random_uuid()::text, legacy.name, '#64748b', true
        FROM (
          SELECT DISTINCT btrim(criticality) AS name
          FROM equipment
          WHERE btrim(coalesce(criticality, '')) <> ''
            AND lower(btrim(criticality)) NOT LIKE 'longo%'
            AND lower(btrim(criticality)) NOT LIKE 'médio%'
            AND lower(btrim(criticality)) NOT LIKE 'medio%'
            AND lower(btrim(criticality)) NOT LIKE 'curto%'
        ) legacy
        ON CONFLICT (name) DO NOTHING
        """
    )
    op.execute(
        """
        UPDATE equipment e
        SET criticality_label_id = c.id
        FROM criticality_label c
        WHERE e.criticality_label_id IS NULL
          AND c.name = btrim(e.criticality)
        """
    )


def downgrade() -> None:
    op.drop_index("equipment_criticality_label_id_idx", table_name="equipment")
    op.drop_constraint("equipment_criticality_label_id_fkey", "equipment", type_="foreignkey")
    op.drop_column("equipment", "criticality_label_id")
    op.drop_table("criticality_label")
    op.drop_column("discipline", "color")
