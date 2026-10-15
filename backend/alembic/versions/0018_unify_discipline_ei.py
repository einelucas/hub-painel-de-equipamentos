"""Centraliza Elétrica e Instrumentação na disciplina única E&I (code EI).

Idempotente e set-based: garante a disciplina EI/"E&I" ativa, reatribui
`equipment.discipline_id` das disciplinas Elétrica/Instrumentação para ela e
desativa (não apaga) as antigas.

Downgrade: no-op documentado. A reatribuição é irreversível (não se sabe mais
qual equipamento era Elétrica e qual era Instrumentação); as disciplinas antigas
permanecem inativas e podem ser reativadas manualmente se necessário.

Revision ID: 0018_unify_discipline_ei
Revises: 0017_monday_apply_job
Create Date: 2026-10-15
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0018_unify_discipline_ei"
down_revision: str | None = "0017_monday_apply_job"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_MATCH = """
    d.id <> (SELECT id FROM discipline WHERE code = 'EI')
    AND (
        upper(d.code) IN ('ELE', 'EL', 'EIA', 'EI-GAP011')
        OR lower(d.name) IN ('elétrica', 'eletrica', 'instrumentação', 'instrumentacao')
    )
"""


def upgrade() -> None:
    # 1. Garante a EI ativa (reaproveita se existir). id texto via gen_random_uuid().
    op.execute(
        """
        INSERT INTO discipline (id, code, name, active)
        SELECT gen_random_uuid()::text, 'EI', 'E&I', true
        WHERE NOT EXISTS (SELECT 1 FROM discipline WHERE code = 'EI')
        """
    )
    op.execute("UPDATE discipline SET name = 'E&I', active = true WHERE code = 'EI'")
    # 2. Reatribui equipamentos em lote.
    op.execute(
        f"""
        UPDATE equipment e
        SET discipline_id = (SELECT id FROM discipline WHERE code = 'EI')
        FROM discipline d
        WHERE e.discipline_id = d.id AND {_OLD_MATCH}
        """
    )
    # 3. Desativa as antigas (sem apagar).
    op.execute(
        f"""
        UPDATE discipline d SET active = false
        WHERE {_OLD_MATCH}
        """
    )


def downgrade() -> None:
    """No-op: a reatribuição é irreversível (ver docstring do módulo)."""
