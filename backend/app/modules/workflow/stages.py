"""Definição declarativa das transições 0–8 e das respectivas pré-condições.

Cada transição do fluxo principal avança exatamente uma etapa. As
pré-condições traduzem o que a especificação observou no processo atual; nada
aqui calcula prazos, índices ou fórmulas ainda não confirmadas pelo negócio.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from app.models.process import (
    Contract,
    LegalProcess,
    Negotiation,
    PurchaseOrder,
    PurchaseRequest,
)

FIRST_STAGE = 0
FINAL_STAGE = 8
REOPEN_STAGE = 1
MIN_REOPEN_SOURCE_STAGE = 2


@dataclass(frozen=True, slots=True)
class ProcessState:
    """Fotografia dos dados do processo usada pelos validadores."""

    negotiation: Negotiation | None = None
    legal: LegalProcess | None = None
    contract: Contract | None = None
    purchase_request: PurchaseRequest | None = None
    purchase_order: PurchaseOrder | None = None


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
            message="Informe o número do contrato.",
            check=lambda state: bool(state.contract and _filled(state.contract.contract_number)),
        ),
        RequirementSpec(
            code="contract_executed_at_required",
            field="contract.executedAt",
            message="Informe a data de escrituração do contrato.",
            check=lambda state: bool(state.contract and _filled(state.contract.executed_at)),
        ),
    ),
    6: (
        RequirementSpec(
            code="purchase_request_kind_required",
            field="purchaseRequest.kind",
            message="Informe se a solicitação é SC ou OCI.",
            check=lambda state: bool(
                state.purchase_request and _filled(state.purchase_request.kind)
            ),
        ),
        RequirementSpec(
            code="purchase_request_number_required",
            field="purchaseRequest.requestNumber",
            message="Informe o número da SC/OCI.",
            check=lambda state: bool(
                state.purchase_request and _filled(state.purchase_request.request_number)
            ),
        ),
        RequirementSpec(
            code="purchase_request_date_required",
            field="purchaseRequest.requestedAt",
            message="Informe a data da SC/OCI.",
            check=lambda state: bool(
                state.purchase_request and _filled(state.purchase_request.requested_at)
            ),
        ),
    ),
    7: (
        RequirementSpec(
            code="purchase_order_number_required",
            field="purchaseOrder.orderNumber",
            message="Informe o número da OC.",
            check=lambda state: bool(
                state.purchase_order and _filled(state.purchase_order.order_number)
            ),
        ),
        RequirementSpec(
            code="purchase_order_date_required",
            field="purchaseOrder.orderedAt",
            message="Informe a data da OC.",
            check=lambda state: bool(
                state.purchase_order and _filled(state.purchase_order.ordered_at)
            ),
        ),
        RequirementSpec(
            code="contract_delivery_at_required",
            field="contract.deliveryAt",
            message="Informe a data de entrega prevista no contrato.",
            check=lambda state: bool(state.contract and _filled(state.contract.delivery_at)),
        ),
    ),
}


def requirements_for(from_stage: int) -> tuple[RequirementSpec, ...]:
    """Requisitos da transição `from_stage -> from_stage + 1`.

    A conclusão (7 -> 8) reexamina os requisitos das etapas anteriores, conforme
    a especificação, consolidando as automações redundantes em uma única regra.
    """
    specs = TRANSITION_REQUIREMENTS.get(from_stage, ())
    if from_stage != FINAL_STAGE - 1:
        return specs
    seen: dict[str, RequirementSpec] = {}
    for stage in range(FIRST_STAGE, FINAL_STAGE):
        for spec in TRANSITION_REQUIREMENTS.get(stage, ()):
            seen.setdefault(spec.code, spec)
    return tuple(seen.values())
