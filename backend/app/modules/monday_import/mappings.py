"""Mapeamentos de colunas e identidades do Monday para conceitos do Hub."""

from __future__ import annotations

from hashlib import sha256
from typing import Final

from app.modules.monday_import.normalization import canonical_header, normalized_name

SOURCE_SYSTEM: Final = "monday"


def _aliases(items: dict[str, str]) -> dict[str, str]:
    return {canonical_header(header): field for header, field in items.items()}


EQUIPMENT_FIELDS: Final = _aliases(
    {
        "Name": "name",
        "Subelementos": "subelements_raw",
        "Status Negociação": "negotiation_status_observed",
        "F.Data Limite Negociação": "negotiation_deadline",
        "Status Necessidade Obra": "work_need_status_observed",
        "F.Limite Entrega Obra": "delivery_deadline",
        "A.Status": "current_stage",
        "0.Fornecedores": "suppliers_raw",
        "0.Origem": "origin",
        "0.Startup/Grãos": "startup_at",
        "0.Disciplina": "discipline_name",
        "F.Data Limite para contrato/OC": "contract_or_po_deadline",
        "0.Criticidade": "criticality_observed",
        "E.Data de Entrega contrato": "contract_delivery_mirror",
        "0.Responsável": "responsible_name",
        "0.Área": "area_name",
        "Work Package": "work_package_codes",
        "1.Equalização": "equalized",
        "2.Data da Negociação": "negotiated_at",
        "3.Data de Abertura do Chamado": "legal_opened_at",
        "3.Chamado Jurídico": "legal_ticket_number",
        "3.Elab. Minuta": "draft_prepared",
        "4.Minuta Aprovada": "draft_approved",
        "5.Data Escrituração": "contract_executed_at",
        "5.Numero Contrato": "contract_number",
        "5.Número Contrato": "contract_number",
        "5.Data de Entrega pelo contrato": "contract_delivery_at",
        "6.Data de SC/OCI": "purchase_request_at",
        "6.Numero SC/OCI": "purchase_request_number",
        "6.Número SC/OCI": "purchase_request_number",
        "7.Data OC": "purchase_order_at",
        "7.Numero OC": "purchase_order_number",
        "7.Número OC": "purchase_order_number",
        "E.Lead Time de Fabricação": "lead_time_days_mirror",
        "Espelho/Fórmula2": "formula2_observed",
        "E.Dias Antes do Startup": "pre_start_days_mirror",
        "ESPELHO-FORMULA-FRETE": "freight_days_mirror",
        "Kickoff": "kickoff_at",
        "Leadtime Negociação": "negotiation_lead_time_observed",
        "Prazo Máximo Negociação": "negotiation_max_days_observed",
        "CAPEX Estimado": "capex_estimated",
    }
)

COMPONENT_FIELDS: Final = _aliases(
    {
        "Subitems": "subitems_marker",
        "Name": "name",
        "TAG": "tag",
        "0.Startup/Grãos": "startup_at",
        "Data Limite de Entrega em Obra": "delivery_deadline",
        "Setor": "sector",
        "Prazo Neg": "negotiation_days_remaining_observed",
        "Data limite para contrato/OC": "contract_or_po_deadline",
        "Lead Time de Fabricação": "lead_time_days",
        "Disponivel Coleta": "collection_available_at",
        "Disponível Coleta": "collection_available_at",
        "0.Dias Antes do Startup": "pre_start_days",
        "Data de Entrega pelo contrato": "contract_delivery_at",
        "Entrega planejada vs negociada": "delivery_margin_days_observed",
        "Status da Data de Entrega": "delivery_status_observed",
        "Arquivos": "files_raw",
        "Frete (Dias)": "freight_days",
        "FÓRMULA-NÃO MEXER": "formula_date_observed",
        "F.Data Limite Negociação_calc": "negotiation_deadline",
        "ID do elemento": "external_id",
    }
)

DATE_FIELDS: Final = {
    "negotiation_deadline",
    "delivery_deadline",
    "startup_at",
    "contract_or_po_deadline",
    "contract_delivery_mirror",
    "negotiated_at",
    "legal_opened_at",
    "contract_executed_at",
    "contract_delivery_at",
    "purchase_request_at",
    "purchase_order_at",
    "kickoff_at",
    "collection_available_at",
    "formula_date_observed",
}
BOOLEAN_FIELDS: Final = {"equalized", "draft_prepared", "draft_approved"}
NONNEGATIVE_INTEGER_FIELDS: Final = {
    "lead_time_days_mirror",
    "pre_start_days_mirror",
    "freight_days_mirror",
    "negotiation_lead_time_observed",
    "negotiation_max_days_observed",
    "lead_time_days",
    "pre_start_days",
    "freight_days",
}
SIGNED_INTEGER_FIELDS: Final = {
    "negotiation_days_remaining_observed",
    "delivery_margin_days_observed",
}


def provisional_equipment_key(name: str) -> str:
    """Chave provisória; project_context é parte da unicidade no banco."""
    return f"normalized-name:{normalized_name(name)}"


def fallback_component_key(parent_key: str, name: str, row_number: int) -> str:
    digest = sha256(f"{parent_key}|{normalized_name(name)}|{row_number}".encode()).hexdigest()[:20]
    return f"missing-external-id:{digest}"
