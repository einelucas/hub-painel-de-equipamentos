"""Contratos da lista mestre e do assistente de criação de obras."""
from __future__ import annotations
from pydantic import Field, model_validator
from app.shared.schema import CamelModel


class MasterComponentOut(CamelModel):
    id: str
    name: str
    requires_quantity_review: bool
    requires_name_review: bool
    active: bool


class MasterAreaOut(CamelModel):
    id: str
    name: str
    is_unassigned: bool
    active: bool


class MasterEquipmentOut(CamelModel):
    id: str
    name: str
    area_ids: list[str]
    review_flags: list[str]
    active: bool
    components: list[MasterComponentOut]


class MasterCatalogOut(CamelModel):
    areas: list[MasterAreaOut]
    equipments: list[MasterEquipmentOut]


class MasterSelectionIn(CamelModel):
    equipment_id: str = Field(min_length=1)
    component_ids: list[str] = Field(default_factory=list)


class MasterProjectCreateIn(CamelModel):
    request_id: str = Field(min_length=8, max_length=80)
    unit_id: str
    name: str = Field(min_length=1, max_length=160)
    code: str | None = Field(default=None, max_length=60)
    selections: list[MasterSelectionIn] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_duplicate_equipments(self) -> MasterProjectCreateIn:
        ids = [selection.equipment_id for selection in self.selections]
        if len(ids) != len(set(ids)):
            raise ValueError("Equipamentos duplicados na seleção")
        for item in self.selections:
            if len(item.component_ids) != len(set(item.component_ids)):
                raise ValueError("Componentes repetidos na seleção")
        return self


class MasterProjectCreatedOut(CamelModel):
    project_context_id: str
    equipments_created: int
    components_created: int
    already_created: bool = False


class MasterCatalogSeedIn(CamelModel):
    schema_version: str
    areas: list[dict]
    equipments: list[dict]
    component_options: list[dict]


class MasterCatalogSeedOut(CamelModel):
    areas_new: int
    equipments_new: int
    components_new: int
    existing: int
    dry_run: bool


class MasterAreaCreateIn(CamelModel):
    name: str = Field(min_length=1, max_length=160)


class MasterEquipmentCreateIn(CamelModel):
    name: str = Field(min_length=1, max_length=200)
    area_ids: list[str] = Field(default_factory=list)


class MasterComponentCreateIn(CamelModel):
    name: str = Field(min_length=1, max_length=500)


class MasterUpdateIn(CamelModel):
    name: str | None = None
    active: bool | None = None


class MasterAreaAssignmentIn(CamelModel):
    area_ids: list[str]
