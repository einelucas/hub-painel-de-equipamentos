"""Contratos estritos do modo de edição em lote (Etapa 01).

Não expõe endpoints nem concede permissões: os futuros handlers deverão validar
EQUIPMENTS_WRITE, isolamento por ProjectContext, catálogos e concorrência.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import ConfigDict, Field, field_validator, model_validator
from pydantic.alias_generators import to_snake

from app.shared.schema import CamelModel

EquipmentEditableField = Literal[
    "discipline_id",
    "responsible_user_id",
    "eap_node_id",
    "work_package_ids",
    "origin",
    "startup_at",
    "criticality_label_id",
]
EditOperation = Literal["SET", "CLEAR", "FILL_EMPTY", "ADD", "REMOVE", "REPLACE"]

_SCALAR_FIELDS = {
    "discipline_id",
    "responsible_user_id",
    "eap_node_id",
    "origin",
    "startup_at",
    "criticality_label_id",
}
_REFERENCE_FIELDS = {
    "discipline_id",
    "responsible_user_id",
    "eap_node_id",
    "criticality_label_id",
}


class StrictBulkModel(CamelModel):
    """Rejeita propriedades extras (inclusive nome, workflow e campos calculados)."""

    model_config = ConfigDict(extra="forbid")


class EquipmentCellChange(StrictBulkModel):
    """Uma intenção explícita sobre um campo de uma linha.

    Ausência de uma mudança != CLEAR. A operação FILL_EMPTY não deve alterar
    valores já preenchidos, mesmo que tenham mudado após a prévia; o backend
    deve rever as versões antes do apply.
    """

    field: EquipmentEditableField
    operation: EditOperation
    value: str | date | list[str] | None = None

    @field_validator("field", mode="before")
    @classmethod
    def normalize_field_name(cls, value: Any) -> Any:
        return to_snake(value) if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_operation(self) -> EquipmentCellChange:
        is_work_package = self.field == "work_package_ids"
        if is_work_package:
            if self.operation not in {"ADD", "REMOVE", "REPLACE", "CLEAR"}:
                raise ValueError("Work Packages exigem ADD, REMOVE, REPLACE ou CLEAR")
            if self.operation == "CLEAR":
                if self.value is not None:
                    raise ValueError("CLEAR não aceita valor")
                return self
            if not isinstance(self.value, list):
                raise ValueError("Work Packages exigem uma lista de IDs")
            if len(self.value) != len(set(self.value)):
                raise ValueError("Work Packages não podem conter IDs duplicados")
            if any(not isinstance(item, str) or not item.strip() for item in self.value):
                raise ValueError("Work Packages exigem IDs válidos")
            if self.operation in {"ADD", "REMOVE"} and not self.value:
                raise ValueError("ADD/REMOVE exigem ao menos um Work Package")
            return self

        if self.field not in _SCALAR_FIELDS or self.operation not in {"SET", "CLEAR", "FILL_EMPTY"}:
            raise ValueError("Operação incompatível com o campo")
        if self.operation == "CLEAR":
            if self.value is not None:
                raise ValueError("CLEAR não aceita valor")
            return self
        if self.field == "startup_at":
            if isinstance(self.value, datetime):
                raise ValueError("Startup exige somente data, sem horário")
            if isinstance(self.value, str):
                try:
                    parsed = date.fromisoformat(self.value)
                except ValueError as exc:
                    raise ValueError("Startup exige data ISO YYYY-MM-DD") from exc
                if len(self.value) != 10:
                    raise ValueError("Startup exige data ISO YYYY-MM-DD")
                self.value = parsed
            if not isinstance(self.value, date):
                raise ValueError("Startup exige data válida")
            return self

        if not isinstance(self.value, str) or not self.value.strip():
            raise ValueError("O campo exige um valor de texto não vazio")
        if self.field in _REFERENCE_FIELDS and len(self.value) > 64:
            raise ValueError("Identificador de catálogo muito longo")
        if self.field == "origin" and len(self.value) > 160:
            raise ValueError("Origem excede 160 caracteres")
        self.value = self.value.strip()
        return self


class EquipmentRowEdit(StrictBulkModel):
    equipment_id: str = Field(min_length=1, max_length=64)
    expected_updated_at: datetime
    changes: list[EquipmentCellChange] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def unique_fields(self) -> EquipmentRowEdit:
        fields = [change.field for change in self.changes]
        if len(fields) != len(set(fields)):
            raise ValueError("Envie somente uma operação por campo e equipamento")
        return self


class EquipmentBulkPreviewIn(StrictBulkModel):
    """Escopo fechado: IDs explícitos de uma única obra, até 100 linhas por lote.

    Seleção por filtros precisa ser resolvida no servidor antes de produzir
    esta lista; nunca confiar em seleção parcial da página do navegador.
    """

    project_context_id: str = Field(min_length=1, max_length=64)
    items: list[EquipmentRowEdit] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def unique_equipment_ids(self) -> EquipmentBulkPreviewIn:
        ids = [item.equipment_id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("Equipamento duplicado no mesmo lote")
        return self


class EquipmentBulkApplyIn(EquipmentBulkPreviewIn):
    """A confirmação referencia a prévia já revisada (token opaco)."""

    preview_token: str = Field(min_length=16, max_length=512)
    idempotency_key: str = Field(min_length=16, max_length=128)


class EquipmentFieldDiffOut(CamelModel):
    equipment_id: str
    field: EquipmentEditableField
    previous_value: Any = None
    proposed_value: Any = None
    skipped_reason: str | None = None


class EquipmentBulkPreviewOut(CamelModel):
    preview_token: str
    requested_count: int
    changed_count: int
    skipped_count: int
    diffs: list[EquipmentFieldDiffOut]
    errors: list[str] = Field(default_factory=list)


class EquipmentBulkApplyOut(CamelModel):
    batch_id: str
    updated_count: int
    skipped_count: int
