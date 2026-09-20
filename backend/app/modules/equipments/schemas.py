from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import Field, field_validator, model_validator

from app.shared.schema import CamelModel


class NamedRefOut(CamelModel):
    id: str
    name: str
    code: str | None = None


class UserRefOut(CamelModel):
    id: str
    name: str
    email: str


class EquipmentCreateIn(CamelModel):
    project_context_id: str
    name: str = Field(min_length=1, max_length=200)
    origin: str | None = Field(default=None, max_length=160)
    startup_at: date | None = None
    discipline_id: str | None = None
    area_id: str | None = None
    work_package_id: str | None = None
    responsible_user_id: str | None = None
    criticality: str | None = Field(default=None, max_length=40)
    capex_estimated: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Nome obrigatório")
        return value


class EquipmentUpdateIn(CamelModel):
    project_context_id: str | None = None
    name: str | None = Field(default=None, min_length=1, max_length=200)
    origin: str | None = Field(default=None, max_length=160)
    startup_at: date | None = None
    discipline_id: str | None = None
    area_id: str | None = None
    work_package_id: str | None = None
    responsible_user_id: str | None = None
    criticality: str | None = Field(default=None, max_length=40)
    capex_estimated: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)

    # `current_stage` é intencionalmente ausente: a etapa só muda pelo serviço de
    # workflow (POST /equipments/{id}/transitions).
    @model_validator(mode="before")
    @classmethod
    def reject_stage_change(cls, data: Any) -> Any:
        if isinstance(data, dict) and ({"currentStage", "current_stage"} & set(data)):
            raise ValueError(
                "A etapa não pode ser alterada por esta rota. "
                "Use POST /equipments/{id}/transitions."
            )
        return data

    @model_validator(mode="after")
    def has_update(self) -> EquipmentUpdateIn:
        if not self.model_fields_set:
            raise ValueError("Informe ao menos um campo para atualizar")
        if self.name is not None and not self.name.strip():
            raise ValueError("Nome obrigatório")
        return self


class EquipmentOut(CamelModel):
    id: str
    name: str
    origin: str | None
    startup_at: date | None
    criticality: str | None
    current_stage: int
    stage_name: str
    capex_estimated: Decimal | None
    project_context: NamedRefOut
    unit: NamedRefOut
    discipline: NamedRefOut | None
    area: NamedRefOut | None
    work_package: NamedRefOut | None
    work_packages: list[NamedRefOut] = Field(default_factory=list)
    responsible_user: UserRefOut | None
    components_count: int
    created_at: datetime
    updated_at: datetime


class PaginationOut(CamelModel):
    page: int
    page_size: int
    total: int
    total_pages: int


class EquipmentListOut(CamelModel):
    items: list[EquipmentOut]
    pagination: PaginationOut


class ComponentCreateIn(CamelModel):
    name: str = Field(min_length=1, max_length=200)
    tag: str | None = Field(default=None, max_length=100)
    startup_at: date | None = None
    sector: str | None = Field(default=None, max_length=120)
    lead_time_days: int | None = Field(default=None, ge=0)
    pre_start_days: int | None = Field(default=None, ge=0)
    contract_delivery_at: date | None = None
    freight_days: int | None = Field(default=None, ge=0)


class ComponentUpdateIn(CamelModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    tag: str | None = Field(default=None, max_length=100)
    startup_at: date | None = None
    sector: str | None = Field(default=None, max_length=120)
    lead_time_days: int | None = Field(default=None, ge=0)
    pre_start_days: int | None = Field(default=None, ge=0)
    contract_delivery_at: date | None = None
    freight_days: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def has_update(self) -> ComponentUpdateIn:
        if not self.model_fields_set:
            raise ValueError("Informe ao menos um campo para atualizar")
        return self


class ComponentOut(CamelModel):
    id: str
    equipment_id: str
    name: str
    tag: str | None
    startup_at: date | None
    sector: str | None
    lead_time_days: int | None
    pre_start_days: int | None
    contract_delivery_at: date | None
    freight_days: int | None
    created_at: datetime
    updated_at: datetime


class ComponentListOut(CamelModel):
    items: list[ComponentOut]


class TransitionOut(CamelModel):
    id: str
    from_stage: int
    from_stage_name: str
    to_stage: int
    to_stage_name: str
    reason: str | None
    actor: UserRefOut | None
    occurred_at: datetime


class EquipmentDetailOut(CamelModel):
    equipment: EquipmentOut
    components: list[ComponentOut]
    history: list[TransitionOut]
