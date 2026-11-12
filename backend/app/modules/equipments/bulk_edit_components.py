"""Contratos estritos para edição em lote de componentes de um único equipamento."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator
from pydantic.alias_generators import to_snake

from app.modules.equipments.bulk_edit_contracts import StrictBulkModel

ComponentEditableField = Literal[
    "tag",
    "sector",
    "startup_at",
    "lead_time_days",
    "pre_start_days",
    "contract_delivery_at",
    "freight_days",
]
ComponentOperation = Literal["SET", "CLEAR", "FILL_EMPTY"]
_DATE_FIELDS = {"startup_at", "contract_delivery_at"}
_INTEGER_FIELDS = {"lead_time_days", "pre_start_days", "freight_days"}
_TEXT_MAX_LENGTH = {"tag": 100, "sector": 120}


class ComponentCellChange(StrictBulkModel):
    field: ComponentEditableField
    operation: ComponentOperation
    value: str | int | date | None = None

    @field_validator("field", mode="before")
    @classmethod
    def normalize_field(cls, value: Any) -> Any:
        return to_snake(value) if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_value(self) -> ComponentCellChange:
        if self.operation == "CLEAR":
            if self.value is not None:
                raise ValueError("CLEAR não pode transportar um valor")
            return self
        if self.field in _DATE_FIELDS:
            if isinstance(self.value, datetime):
                raise ValueError("Informe somente a data, sem horário")
            if isinstance(self.value, str):
                if len(self.value) != 10:
                    raise ValueError("Data deve estar no formato YYYY-MM-DD")
                try:
                    self.value = date.fromisoformat(self.value)
                except ValueError as exc:
                    raise ValueError("Data inválida") from exc
            if not isinstance(self.value, date):
                raise ValueError("Data obrigatória")
        elif self.field in _INTEGER_FIELDS:
            if type(self.value) is not int or self.value < 0:
                raise ValueError("Dias devem ser um inteiro não negativo")
        else:
            if not isinstance(self.value, str) or not self.value.strip():
                raise ValueError("Informe texto não vazio")
            if len(self.value.strip()) > _TEXT_MAX_LENGTH[self.field]:
                raise ValueError("Texto excede o limite do campo")
            self.value = self.value.strip()
        return self


class ComponentRowEdit(StrictBulkModel):
    component_id: str = Field(min_length=1, max_length=64)
    expected_updated_at: datetime
    changes: list[ComponentCellChange] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def no_duplicate_fields(self) -> ComponentRowEdit:
        fields = [change.field for change in self.changes]
        if len(fields) != len(set(fields)):
            raise ValueError("Campo repetido para o mesmo componente")
        return self


class ComponentBulkPreviewIn(StrictBulkModel):
    items: list[ComponentRowEdit] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def no_duplicate_items(self) -> ComponentBulkPreviewIn:
        ids = [row.component_id for row in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("Componente repetido no mesmo lote")
        return self


class ComponentBulkApplyIn(ComponentBulkPreviewIn):
    preview_token: str = Field(min_length=16, max_length=512)
    idempotency_key: str = Field(min_length=16, max_length=128)


class ComponentFieldDiffOut(StrictBulkModel):
    component_id: str
    field: ComponentEditableField
    previous_value: Any = None
    proposed_value: Any = None
    skipped_reason: str | None = None


class ComponentBulkPreviewOut(StrictBulkModel):
    preview_token: str
    requested_count: int
    changed_count: int
    skipped_count: int
    diffs: list[ComponentFieldDiffOut]
    errors: list[str] = Field(default_factory=list)
