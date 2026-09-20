from __future__ import annotations

from pydantic import Field

from app.shared.schema import CamelModel


class ResponsibleOut(CamelModel):
    id: str
    name: str
    email: str


class ResponsibleListOut(CamelModel):
    items: list[ResponsibleOut]


class UnitRefOut(CamelModel):
    id: str
    code: str
    name: str


class UserUnitsOut(CamelModel):
    user_id: str
    role: str
    # ADMIN enxerga todas as unidades por perfil, sem depender de vínculo.
    all_units: bool
    units: list[UnitRefOut]


class UserUnitsUpdateIn(CamelModel):
    unit_ids: list[str] = Field(default_factory=list)
