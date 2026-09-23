"""Definição declarativa das transições 0–8 e das respectivas pré-condições.

Cada transição do fluxo principal avança exatamente uma etapa. As
pré-condições traduzem o que a especificação observou no processo atual; nada
aqui calcula prazos, índices ou fórmulas ainda não confirmadas pelo negócio.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import TypeVar

from app.models.equipment import Equipment
from app.models.process import (
    Contract,
    LegalProcess,
    Negotiation,
    PurchaseOrder,
    PurchaseRequest,
)

FIRST_STAGE = 0
FINAL_STAGE = 8


@dataclass(frozen=True, slots=True)
class ProcessState:
    """Fotografia dos dados do processo usada pelos validadores.

    Etapa 7A: Contract/PurchaseRequest/PurchaseOrder são 1:N — os
    validadores de fase tratam "preenchido" como "existe pelo menos um
    registro com o campo preenchido" (nenhuma fórmula nova, só adaptado à
    nova cardinalidade). `equipment` carrega os campos que passaram a viver
    no próprio Equipment (ex.: janela de entrega contratual)."""

    negotiation: Negotiation | None = None
    legal: LegalProcess | None = None
    contracts: Sequence[Contract] = field(default_factory=tuple)
    purchase_requests: Sequence[PurchaseRequest] = field(default_factory=tuple)
    purchase_orders: Sequence[PurchaseOrder] = field(default_factory=tuple)
    equipment: Equipment | None = None
    # Etapa 7A: fornecedor é único por equipamento (EquipmentSupplier, no
    # máximo 1 vínculo) — só a existência importa para a regra de conclusão.
    has_supplier: bool = False


@dataclass(frozen=True, slots=True)
class RequirementSpec:
    code: str
    field: str
    message: str
    check: Callable[[ProcessState], bool]


def _filled(value: object | None) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


_T = TypeVar("_T")


def _any_filled(items: Sequence[_T], getter: Callable[[_T], object | None]) -> bool:
    """Etapa 7A: com Contract/PurchaseRequest/PurchaseOrder 1:N, um requisito
    conta como satisfeito quando QUALQUER registro do equipamento tem o
    campo preenchido — nenhum threshold novo, só adaptado à cardinalidade."""
    return any(_filled(getter(item)) for item in items)


# GAP dispensado por tipo de exceção (Etapa 7B) — usado por
# `workflow/service.py` para marcar como satisfeitos os requisitos que a
# exceção explicitamente dispensa enquanto ela estiver ACTIVE. Nunca um
# `force=true` genérico: só estes códigos, só para este tipo.
EXCEPTION_DISPENSED_REQUIREMENT_CODES: dict[str, frozenset[str]] = {
    # Fornecedor pré-definido: não há negociação real a confirmar.
    "FIXED_SUPPLIER": frozenset({"negotiation_equalized_required", "negotiation_date_required"}),
    # Importação: sem obrigatoriedade de contrato nem SC/OCI (mas continuam
    # preenchíveis normalmente — só deixam de bloquear o avanço).
    "IMPORTATION": frozenset(
        {
            "contract_number_required",
            "contract_executed_at_required",
            "purchase_request_kind_required",
            "purchase_request_number_required",
            "purchase_request_date_required",
        }
    ),
}


# from_stage -> requisitos para avançar até from_stage + 1.
TRANSITION_REQUIREMENTS: dict[int, tuple[RequirementSpec, ...]] = {
    0: (),
    1: (
        RequirementSpec(
            code="negotiation_equalized_required",
            field="negotiation.equalized",
            message="Confirme a equalização da negociação.",
            check=lambda state: bool(state.negotiation and state.negotiation.equalized),
        ),
    ),
    2: (
        RequirementSpec(
            code="negotiation_date_required",
            field="negotiation.negotiatedAt",
            message="Informe a data da negociação.",
            check=lambda state: bool(state.negotiation and _filled(state.negotiation.negotiated_at)),
        ),
    ),
    3: (
        RequirementSpec(
            code="legal_opened_at_required",
            field="legal.openedAt",
            message="Informe a data de abertura do chamado jurídico.",
            check=lambda state: bool(state.legal and _filled(state.legal.opened_at)),
        ),
        RequirementSpec(
            code="legal_ticket_number_required",
            field="legal.ticketNumber",
            message="Informe o número do chamado jurídico.",
            check=lambda state: bool(state.legal and _filled(state.legal.ticket_number)),
        ),
    ),
    4: (
        RequirementSpec(
            code="legal_draft_prepared_required",
            field="legal.draftPrepared",
            message="Confirme que a minuta foi elaborada.",
            check=lambda state: bool(state.legal and state.legal.draft_prepared),
        ),
        RequirementSpec(
            code="legal_draft_approved_required",
            field="legal.draftApproved",
            message="Confirme que a minuta foi aprovada.",
            check=lambda state: bool(state.legal and state.legal.draft_approved),
        ),
    ),
    5: (
        RequirementSpec(
            code="contract_number_required",
            field="contract.contractNumber",
            message="Informe o número de ao menos um contrato.",
            check=lambda state: _any_filled(state.contracts, lambda c: c.contract_number),
        ),
        RequirementSpec(
            code="contract_executed_at_required",
            field="contract.executedAt",
            message="Informe a data de escrituração de ao menos um contrato.",
            check=lambda state: _any_filled(state.contracts, lambda c: c.executed_at),
        ),
    ),
    6: (
        RequirementSpec(
            code="purchase_request_kind_required",
            field="purchaseRequest.kind",
            message="Informe se a solicitação é SC ou OCI.",
            check=lambda state: _any_filled(state.purchase_requests, lambda r: r.kind),
        ),
        RequirementSpec(
            code="purchase_request_number_required",
            field="purchaseRequest.requestNumber",
            message="Informe o número de ao menos uma SC/OCI.",
            check=lambda state: _any_filled(state.purchase_requests, lambda r: r.request_number),
        ),
        RequirementSpec(
            code="purchase_request_date_required",
            field="purchaseRequest.requestedAt",
            message="Informe a data de ao menos uma SC/OCI.",
            check=lambda state: _any_filled(state.purchase_requests, lambda r: r.requested_at),
        ),
    ),
    # `7` não existe aqui de propósito: a transição 7 -> 8 (conclusão) não usa
    # mais requisitos "por fase" — usa `COMPLETION_REQUIREMENTS` abaixo,
    # `requirements_for` trata `from_stage == FINAL_STAGE - 1` como caso
    # especial antes de consultar este dicionário.
}

# Etapa 7, seção 6 — regra de conclusão (7 -> 8), substitui a antiga
# reexecução de todos os requisitos anteriores: precisa estar efetivamente
# na fase 7, ter fornecedor, ter pelo menos uma OC e ter o valor total do
# projeto preenchido. Nenhuma dessas quatro é dispensável por exceção.
COMPLETION_REQUIREMENTS: tuple[RequirementSpec, ...] = (
    RequirementSpec(
        code="completion_supplier_required",
        field="equipment.supplier",
        message="Informe o fornecedor do equipamento antes de concluir.",
        check=lambda state: state.has_supplier,
    ),
    RequirementSpec(
        code="completion_purchase_order_required",
        field="purchaseOrder",
        message="É necessário pelo menos uma Ordem de Compra para concluir.",
        check=lambda state: len(state.purchase_orders) > 0,
    ),
    RequirementSpec(
        code="completion_project_total_value_required",
        field="equipment.projectTotalValue",
        message="Informe o Valor Total do Projeto antes de concluir.",
        check=lambda state: bool(
            state.equipment and _filled(state.equipment.project_total_value)
        ),
    ),
)


def dispensed_codes(exception_type: str | None) -> frozenset[str]:
    """Códigos de requisito dispensados pela exceção ATIVA (se houver)."""
    if exception_type is None:
        return frozenset()
    return EXCEPTION_DISPENSED_REQUIREMENT_CODES.get(exception_type, frozenset())


def requirements_for(from_stage: int) -> tuple[RequirementSpec, ...]:
    """Requisitos da transição `from_stage -> from_stage + 1`.

    Etapa 7, seção 6: a conclusão (7 -> 8) NÃO reexamina mais os requisitos
    de todas as fases anteriores — usa a regra explícita e mais simples do
    negócio: fornecedor + pelo menos uma OC + Valor Total do Projeto
    preenchido (`COMPLETION_REQUIREMENTS`). O equipamento já ter chegado
    efetivamente à fase 7 é garantido pela própria state machine (só se
    avança uma fase por vez, nunca por salto).
    """
    if from_stage == FINAL_STAGE - 1:
        return COMPLETION_REQUIREMENTS
    return TRANSITION_REQUIREMENTS.get(from_stage, ())
