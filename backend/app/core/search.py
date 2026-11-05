"""Busca textual tolerante a acentos.

A extensão `unaccent` do PostgreSQL é habilitada pela migration
`0030_unaccent_search`. O termo também passa por `unaccent`, então tanto
`incendio` quanto `incêndio` encontram os registros com as duas grafias.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import ColumnElement, func


def unaccent_ilike(column: Any, term: str) -> ColumnElement[bool]:
    """Compara `column` com `term` ignorando acentos e caixa."""
    pattern = f"%{term.strip()}%"
    return func.unaccent(column).ilike(func.unaccent(pattern))
