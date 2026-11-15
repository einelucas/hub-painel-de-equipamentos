"""Contratos REST do simulador (camelCase, como os demais módulos)."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import Field, field_validator

from app.shared.schema import CamelModel


class NamedSimulationIn(CamelModel):
    name: str = Field(min_length=1, max_length=160)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        stripped = " ".join(value.split())
        if not stripped:
            raise ValueError("Informe um nome válido")
        return stripped


class SimulationUnitOut(CamelModel):
    id: str
    name: str


class SimulationProjectOut(CamelModel):
    id: str
    unit_id: str
    name: str


class SimulationUnitListOut(CamelModel):
    items: list[SimulationUnitOut]


class SimulationProjectListOut(CamelModel):
    items: list[SimulationProjectOut]


class ScenarioItemIn(CamelModel):
    name: str = Field(min_length=1, max_length=500)
    origin: str | None = Field(default=None, max_length=160)
    discipline: str | None = Field(default=None, max_length=160)
    supplier: str | None = Field(default=None, max_length=200)
    area: str | None = Field(default=None, max_length=160)
    responsible: str | None = Field(default=None, max_length=160)
    startup_at: date | None = None
    supplies_days: int | None = Field(default=None, ge=0, le=36500)
    legal_days: int | None = Field(default=None, ge=0, le=36500)
    manufacture_days: int | None = Field(default=None, ge=0, le=36500)
    pre_start_days: int | None = Field(default=None, ge=0, le=36500)


class ScenarioCreateIn(CamelModel):
    simulation_project_id: str
    name: str = Field(min_length=1, max_length=120)
    startup_at: date
    source: Literal["EXCEL", "MANUAL"] = "MANUAL"
    items: list[ScenarioItemIn] = Field(default_factory=list, max_length=500)


class ScenarioUpdateIn(CamelModel):
    name: str = Field(min_length=1, max_length=120)
    startup_at: date
    items: list[ScenarioItemIn] = Field(max_length=500)


class ScenarioCloneIn(CamelModel):
    name: str = Field(min_length=1, max_length=120)
    startup_at: date


class ScenarioItemOut(ScenarioItemIn):
    id: str
    delivery_deadline: date | None
    contract_deadline: date | None
    negotiation_deadline: date | None


class MonthlyOut(CamelModel):
    month: str
    negotiations: int
    contracts: int
    deliveries: int


class ScenarioSummaryOut(CamelModel):
    equipments: int
    negotiations_calculated: int
    contracts_calculated: int
    deliveries_calculated: int
    first_negotiation: date | None
    last_negotiation: date | None
    first_delivery: date | None
    last_delivery: date | None
    average_manufacture_days: float | None
    average_pre_start_days: float | None
    monthly: list[MonthlyOut]


class ScenarioOut(CamelModel):
    id: str
    simulation_project_id: str
    name: str
    startup_at: date
    source: str
    created_at: datetime
    updated_at: datetime
    items: list[ScenarioItemOut]
    summary: ScenarioSummaryOut


class ScenarioListOut(CamelModel):
    items: list[ScenarioOut]
