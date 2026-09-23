from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import Field, field_validator, model_validator

from app.domain.equipment_calculations import NegotiationStatus, WorkNeedStatus
from app.shared.schema import CamelModel


class NamedRefOut(CamelModel):
    id: str
    name: str
    code: str | None = None


class UserRefOut(CamelModel):
    id: str
    name: str
    email: str


def _no_duplicate_work_packages(value: list[str] | None) -> list[str] | None:
    if value is None:
        return value
    if len(set(value)) != len(value):
        raise ValueError("workPackageIds não pode conter IDs duplicados")
    return value


# FUN-001 — nenhum destes é aceito em Create/Update: são sempre consequência
# dos campos-base (startup, prazos dos componentes), nunca informados
# manualmente. Ver `_reject_calculated_fields`.
_EQUIPMENT_CALCULATED_FIELDS = {
    "maxLeadTimeDays",
    "max_lead_time_days",
    "maxPreStartDays",
    "max_pre_start_days",
    "maxFreightDays",
    "max_freight_days",
    "deliveryDeadline",
    "delivery_deadline",
    "contractOrderDeadline",
    "contract_order_deadline",
    "negotiationDeadline",
    "negotiation_deadline",
    "negotiationDaysRemaining",
    "negotiation_days_remaining",
    "negotiationStatus",
    "negotiation_status",
    "workNeedDaysRemaining",
    "work_need_days_remaining",
    "workNeedStatus",
    "work_need_status",
}
_COMPONENT_CALCULATED_FIELDS = {
    "deliveryDeadline",
    "delivery_deadline",
    "availableForCollection",
    "available_for_collection",
    "contractOrderDeadline",
    "contract_order_deadline",
    "negotiationDeadline",
    "negotiation_deadline",
    "negotiationDaysRemaining",
    "negotiation_days_remaining",
    "deliveryMarginDays",
    "delivery_margin_days",
}


def _reject_calculated_fields(data: Any, forbidden: set[str]) -> Any:
    if isinstance(data, dict):
        present = forbidden & set(data)
        if present:
            raise ValueError(
                f"Campo(s) calculado(s) não podem ser informados diretamente: {sorted(present)}"
            )
    return data


def _validate_delivery_window(start: date | None, end: date | None) -> None:
    if start is not None and end is not None and start > end:
        raise ValueError("A data inicial da janela de entrega não pode ser depois da final")


class EquipmentCreateIn(CamelModel):
    project_context_id: str
    name: str = Field(min_length=1, max_length=200)
    origin: str | None = Field(default=None, max_length=160)
    startup_at: date | None = None
    discipline_id: str | None = None
    area_id: str | None = None
    # `work_package_ids` é o contrato oficial (0..N, relação N:N via
    # `equipment_work_package`). O campo legado singular `work_package_id`
    # não é aceito aqui — ver `Equipment.work_package_id` para o porquê ele
    # ainda existe na coluna do banco.
    work_package_ids: list[str] = Field(default_factory=list)
    responsible_user_id: str | None = None
    criticality: str | None = Field(default=None, max_length=40)
    capex_estimated: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    # Etapa 7A: preenchidos manualmente — nunca calculados a partir da soma
    # das OCs nem de fórmula alguma.
    project_total_value: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    contractual_delivery_start: date | None = None
    contractual_delivery_end: date | None = None

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Nome obrigatório")
        return value

    @field_validator("work_package_ids")
    @classmethod
    def work_package_ids_no_duplicates(cls, value: list[str] | None) -> list[str] | None:
        return _no_duplicate_work_packages(value)

    @model_validator(mode="after")
    def delivery_window_order(self) -> EquipmentCreateIn:
        _validate_delivery_window(self.contractual_delivery_start, self.contractual_delivery_end)
        return self

    @model_validator(mode="before")
    @classmethod
    def reject_calculated_fields(cls, data: Any) -> Any:
        return _reject_calculated_fields(data, _EQUIPMENT_CALCULATED_FIELDS)

    @model_validator(mode="before")
    @classmethod
    def reject_operational_status(cls, data: Any) -> Any:
        return _reject_calculated_fields(data, {"operationalStatus", "operational_status"})


class EquipmentUpdateIn(CamelModel):
    project_context_id: str | None = None
    name: str | None = Field(default=None, min_length=1, max_length=200)
    origin: str | None = Field(default=None, max_length=160)
    startup_at: date | None = None
    discipline_id: str | None = None
    area_id: str | None = None
    # Ausente no PATCH -> vínculos N:N não são tocados. `[]` explícito ->
    # remove todos os vínculos. Ver nota acima sobre `work_package_id` legado.
    work_package_ids: list[str] | None = None
    responsible_user_id: str | None = None
    criticality: str | None = Field(default=None, max_length=40)
    capex_estimated: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    project_total_value: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    contractual_delivery_start: date | None = None
    contractual_delivery_end: date | None = None

    @field_validator("work_package_ids")
    @classmethod
    def work_package_ids_no_duplicates(cls, value: list[str] | None) -> list[str] | None:
        return _no_duplicate_work_packages(value)

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

    @model_validator(mode="before")
    @classmethod
    def reject_calculated_fields(cls, data: Any) -> Any:
        return _reject_calculated_fields(data, _EQUIPMENT_CALCULATED_FIELDS)

    @model_validator(mode="before")
    @classmethod
    def reject_operational_status(cls, data: Any) -> Any:
        # Etapa 7B: `operational_status` só muda pelos serviços dedicados
        # (Standby/Cancelado/Saneamento), nunca por este PATCH genérico —
        # cada mudança precisa de justificativa auditável.
        return _reject_calculated_fields(data, {"operationalStatus", "operational_status"})

    @model_validator(mode="after")
    def has_update(self) -> EquipmentUpdateIn:
        if not self.model_fields_set:
            raise ValueError("Informe ao menos um campo para atualizar")
        if self.name is not None and not self.name.strip():
            raise ValueError("Nome obrigatório")
        _validate_delivery_window(self.contractual_delivery_start, self.contractual_delivery_end)
        return self


class EquipmentCalculatedOut(CamelModel):
    """Prazos e agregações derivadas dos componentes (FUN-001). Somente
    leitura — nunca aceitos em Create/Update, sempre recalculados a partir
    dos campos-base. `None` quando faltar dado-base obrigatório ou não
    houver componente com o dado preenchido; nunca um zero/data inventada."""

    max_lead_time_days: int | None
    max_pre_start_days: int | None
    max_freight_days: int | None
    delivery_deadline: date | None
    contract_order_deadline: date | None
    negotiation_deadline: date | None
    # Dinâmico: depende da data de referência (hoje, UTC) usada no momento
    # da consulta — nunca persistido, recalculado a cada leitura.
    negotiation_days_remaining: int | None
    # GAP-014 (Etapa 6C): enum estável, nunca os rótulos/emoji do Monday.
    # `None` quando não há `negotiationDeadline` nem `negotiatedAt` (nada
    # para classificar ainda).
    negotiation_status: NegotiationStatus | None
    # Etapa 6C.1 — "Status Necessidade da Obra": mesma data-base
    # (`delivery_deadline` acima), dinâmico, nunca persistido. `None`
    # quando `delivery_deadline` é `None`.
    work_need_days_remaining: int | None
    work_need_status: WorkNeedStatus | None


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
    # DEPRECATED: espelho do FK legado `equipment.work_package_id` (0..1).
    # Não é mais escrito por create/update; só existe porque a migração do
    # Monday ainda o preenche quando a origem trazia exatamente 1 Work
    # Package. Novas telas devem ler `work_packages` (N:N), não este campo.
    # Candidato a remoção quando o CRUD legado que ainda o lê for desligado.
    work_package: NamedRefOut | None
    work_packages: list[NamedRefOut] = Field(default_factory=list)
    responsible_user: UserRefOut | None
    # Etapa 7A: fornecedor único do equipamento (no máximo 1 vínculo ativo
    # — ver `app.models.supplier`). `None` quando ainda não há fornecedor.
    supplier: NamedRefOut | None = None
    # Etapa 7 — estado operacional, separado da fase (`current_stage`).
    # Só muda pelos serviços dedicados de Standby/Cancelado/Saneamento.
    operational_status: str = "ACTIVE"
    # Preenchido manualmente; nunca calculado a partir da soma das OCs.
    project_total_value: Decimal | None = None
    # Janela de entrega contratual (De/Até) — pertence ao equipamento, não a
    # um contrato individual.
    contractual_delivery_start: date | None = None
    contractual_delivery_end: date | None = None
    components_count: int
    calculated: EquipmentCalculatedOut
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

    @model_validator(mode="before")
    @classmethod
    def reject_calculated_fields(cls, data: Any) -> Any:
        return _reject_calculated_fields(data, _COMPONENT_CALCULATED_FIELDS)


class ComponentUpdateIn(CamelModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    tag: str | None = Field(default=None, max_length=100)
    startup_at: date | None = None
    sector: str | None = Field(default=None, max_length=120)
    lead_time_days: int | None = Field(default=None, ge=0)
    pre_start_days: int | None = Field(default=None, ge=0)
    contract_delivery_at: date | None = None
    freight_days: int | None = Field(default=None, ge=0)

    @model_validator(mode="before")
    @classmethod
    def reject_calculated_fields(cls, data: Any) -> Any:
        return _reject_calculated_fields(data, _COMPONENT_CALCULATED_FIELDS)

    @model_validator(mode="after")
    def has_update(self) -> ComponentUpdateIn:
        if not self.model_fields_set:
            raise ValueError("Informe ao menos um campo para atualizar")
        return self


class ComponentCalculatedOut(CamelModel):
    """Prazos derivados do componente (FUN-001). Depende só do startup
    PRÓPRIO do componente — nunca herda `equipment.startup_at`. `None`
    quando faltar startup/pré-start/lead time (frete em branco vale 0 dias,
    comportamento já confirmado na migração — ver
    `app/domain/equipment_calculations.py`)."""

    delivery_deadline: date | None
    available_for_collection: date | None
    contract_order_deadline: date | None
    negotiation_deadline: date | None
    negotiation_days_remaining: int | None
    delivery_margin_days: int | None


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
    calculated: ComponentCalculatedOut
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
