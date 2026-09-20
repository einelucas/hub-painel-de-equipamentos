from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.shared.schema import CamelModel


class UnitOut(CamelModel):
    id: str
    code: str
    name: str
    active: bool
    created_at: datetime
    updated_at: datetime


class ProjectContextOut(CamelModel):
    id: str
    unit_id: str
    code: str
    name: str
    active: bool


class AreaOut(CamelModel):
    id: str
    unit_id: str
    name: str
    active: bool


class DisciplineOut(CamelModel):
    id: str
    code: str
    name: str
    active: bool


class WorkPackageOut(CamelModel):
    id: str
    project_context_id: str
    code: str
    name: str
    active: bool


class CatalogListOut(CamelModel):
    items: list[UnitOut | ProjectContextOut | AreaOut | DisciplineOut | WorkPackageOut]


class UnitCreateIn(CamelModel):
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=160)


class ProjectContextCreateIn(CamelModel):
    code: str = Field(min_length=1, max_length=60)
    name: str = Field(min_length=1, max_length=160)


class AreaCreateIn(CamelModel):
    unit_id: str
    name: str = Field(min_length=1, max_length=160)


class DisciplineCreateIn(CamelModel):
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=160)


class WorkPackageCreateIn(CamelModel):
    project_context_id: str
    code: str = Field(min_length=1, max_length=60)
    name: str = Field(min_length=1, max_length=160)
