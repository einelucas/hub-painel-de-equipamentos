"""Normaliza a disciplina unificada para code "E&I", name "Elétrica e Instrumentação".

A 0018 criou a disciplina com code `EI` e name `E&I`. A UI exibe "CODE · Nome", e o
desejado é "E&I · Elétrica e Instrumentação". Esta migration é idempotente e set-based:

1. Se NÃO existe linha com code 'E&I', a linha legada (code 'EI', ou name 'E&I') é
   renomeada in-place (preserva o id e os equipamentos já vinculados).
2. Se não existe nenhuma, a linha é criada.
3. Colisão (já existem 'E&I' e 'EI'): a linha 'E&I' é a canônica; os equipamentos das
   linhas legadas são reatribuídos a ela e as legadas são desativadas e renomeadas
   (sem DELETE; o `code` delas não muda, então o UNIQUE não é violado).
4. A linha canônica fica ativa, com name 'Elétrica e Instrumentação'.

Downgrade: reverte code/name da linha canônica para EI / E&I quando não há linha 'EI'
(se houver, o UNIQUE seria violado; nesse caso o downgrade só reverte o name).

Revision ID: 0019_discipline_ei_code_name
Revises: 0018_unify_discipline_ei
Create Date: 2026-10-15
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0019_discipline_ei_code_name"
down_revision: str | None = "0018_unify_discipline_ei"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LEGACY_MATCH = """
    d.code <> 'E&I'
    AND (d.code = 'EI' OR d.name = 'E&I' OR d.code = 'EI-GAP011')
"""


def upgrade() -> None:
    # 1. Renomeia a linha legada in-place quando ainda não há 'E&I' (sem colisão).
    op.execute(
        """
        UPDATE discipline SET code = 'E&I'
        WHERE id = (
            SELECT id FROM discipline
            WHERE code = 'EI' OR name = 'E&I'
            ORDER BY (code = 'EI') DESC, id
            LIMIT 1
        )
        AND NOT EXISTS (SELECT 1 FROM discipline WHERE code = 'E&I')
        """
    )
    # 2. Cria quando nenhuma existe.
    op.execute(
        """
        INSERT INTO discipline (id, code, name, active)
        SELECT gen_random_uuid()::text, 'E&I', 'Elétrica e Instrumentação', true
        WHERE NOT EXISTS (SELECT 1 FROM discipline WHERE code = 'E&I')
        """
    )
    # 3. Normaliza a canônica.
    op.execute("UPDATE discipline SET name = 'Elétrica e Instrumentação', active = true WHERE code = 'E&I'")
    # 4. Colisão: reatribui equipamentos das linhas legadas restantes à canônica.
    op.execute(
        f"""
        UPDATE equipment e
        SET discipline_id = (SELECT id FROM discipline WHERE code = 'E&I')
        FROM discipline d
        WHERE e.discipline_id = d.id AND {_LEGACY_MATCH}
        """
    )
    # 5. Desativa e renomeia as legadas (sem apagar; o code delas permanece).
    op.execute(
        f"""
        UPDATE discipline d
        SET active = false, name = 'Elétrica e Instrumentação (legado)'
        WHERE {_LEGACY_MATCH}
        """
    )


def downgrade() -> None:
    """Reverte para code EI / name E&I quando não há linha 'EI' (UNIQUE em code)."""
    op.execute(
        """
        UPDATE discipline SET code = 'EI', name = 'E&I'
        WHERE code = 'E&I' AND NOT EXISTS (SELECT 1 FROM discipline WHERE code = 'EI')
        """
    )
    op.execute("UPDATE discipline SET name = 'E&I' WHERE code = 'E&I'")
