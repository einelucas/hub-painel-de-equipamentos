"""Conceitos canônicos do importador Monday e chaves de identidade.

Os cabeçalhos de ORIGEM (aliases) não ficam aqui: pertencem ao ImportProfile
(`profile.py`, `profiles/*.json`). Este módulo define apenas os CONCEITOS
canônicos que o pipeline entende e a semântica de tipo de cada um, usada pela
normalização — igual para qualquer board.
"""

from __future__ import annotations

from hashlib import sha256
from typing import Final

from app.modules.monday_import.normalization import normalized_name

SOURCE_SYSTEM: Final = "monday"

# Conceitos canônicos aceitos em cada nível. Um profile só pode apontar
# cabeçalhos da origem para estes nomes; o plan/apply lê exatamente eles.
EQUIPMENT_CONCEPTS: Final = frozenset(
    {
        "name",
        "external_id",
        "subelements_raw",
        "current_stage",
        "negotiation_status_observed",
        "negotiation_deadline",
        "work_need_status_observed",
        "delivery_deadline",
        "suppliers_raw",
        "supplier_corporate_code",
        "origin",
        "startup_at",
        "discipline_name",
        "contract_or_po_deadline",
        "criticality_observed",
        "contract_delivery_mirror",
        "responsible_name",
        "responsible_legacy_text",
        "area_name",
        "area_legacy_text",
        "work_package_codes",
        "equalized",
        "negotiated_at",
        "legal_opened_at",
        "legal_ticket_number",
        "draft_prepared",
        "draft_approved",
        "contract_executed_at",
        "contract_number",
        "contract_delivery_at",
        "purchase_request_at",
        "purchase_request_number",
        "purchase_order_at",
        "purchase_order_number",
        "lead_time_days_mirror",
        "formula2_observed",
        "pre_start_days_mirror",
        "freight_days_mirror",
        "kickoff_at",
        "negotiation_lead_time_observed",
        "negotiation_max_days_observed",
        "capex_estimated",
        # Candidato a CAPEX ainda não validado: campo próprio para que o
        # plan/apply NUNCA o grave como capex_estimated.
        "planned_cost_candidate",
    }
)
COMPONENT_CONCEPTS: Final = frozenset(
    {
        "subitems_marker",
        "name",
        "external_id",
        "tag",
        "startup_at",
        "delivery_deadline",
        "sector",
        "negotiation_days_remaining_observed",
        "contract_or_po_deadline",
        "lead_time_days",
        "collection_available_at",
        "pre_start_days",
        "contract_delivery_at",
        "delivery_margin_days_observed",
        "delivery_status_observed",
        "files_raw",
        "freight_days",
        "formula_date_observed",
        "negotiation_deadline",
    }
)

DATE_FIELDS: Final = {
    "negotiation_deadline",
    "delivery_deadline",
    "startup_at",
    "contract_or_po_deadline",
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
# Espelhos do Monday que listam as datas dos subitens ("2027-01-10, 2027-02-03"):
# lista de datas distintas, nunca forçada a uma data única.
DATE_LIST_FIELDS: Final = {"contract_delivery_mirror"}
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


def parent_name_ordinal_component_key(parent_key: str, name: str, ordinal: int) -> str:
    """Identidade de subitem sem ID do elemento (profile `identity_fallback`).

    Não depende da linha da planilha: o mesmo equipamento em outro arquivo de
    fase, ou com outros equipamentos acima, mantém a mesma chave. O ordinal só
    distingue irmãos com o MESMO nome normalizado, na ordem em que aparecem."""
    digest = sha256(f"{parent_key}|{normalized_name(name)}|{ordinal}".encode()).hexdigest()[:20]
    return f"parent-name-ordinal:{digest}"
