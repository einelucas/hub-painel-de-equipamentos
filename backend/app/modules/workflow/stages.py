"""Definição declarativa das transições 0–8 e das respectivas pré-condições.

Cada transição do fluxo principal avança exatamente uma etapa. As
pré-condições traduzem o que a especificação observou no processo atual; nada
aqui calcula prazos, índices ou fórmulas ainda não confirmadas pelo negócio.

Etapa 7.1: os requisitos de cada fase são agrupados (`RequirementGroupSpec`)
em vez de campos soltos. Um grupo incompleto bloqueia o avanço a menos que
exista um `RequirementWaiver` ACTIVE para aquele equipamento/fase/grupo
(ver `app.modules.workflow.waivers`) — só os grupos marcados `waivable=True`
aqui podem receber dispensa; o backend é a única fonte de verdade sobre
quais grupos existem e quais são dispensáveis, nunca uma string arbitrária
vinda do cliente.
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

# Etapa 7.1 — motivos de dispensa: só classificação/auditoria, nunca
# determinam quais grupos/fases são dispensáveis (isso é fixo abaixo).
REASON_CODES = ("IMPORTATION", "FIXED_SUPPLIER", "EXCEPTIONAL_PROCESS", "OTHER")


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
class RequirementGroupSpec:
    code: str
    stage: int
    label: str
    message: str
    waivable: bool
    fields: tuple[str, ...]
    check: Callable[[ProcessState], bool]


def _filled(value: object | None) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


_T = TypeVar("_T")


def _any_filled(items: Sequence[_T], getter: Callable[[_T], object | None]) -> bool:
    return any(_filled(getter(item)) for item in items)


def _any_complete(items: Sequence[_T], *getters: Callable[[_T], object | None]) -> bool:
    """Etapa 7.1: um grupo 1:N só conta como satisfeito quando existe UM
    ÚNICO registro com TODOS os campos exigidos preenchidos — nunca
    combinando, por exemplo, o número de um contrato com a data de
    escrituração de outro."""
    return any(all(_filled(getter(item)) for getter in getters) for item in items)


# from_stage -> grupos de requisitos que precisam estar SATISFIED ou WAIVED
# para avançar até from_stage + 1.
GROUPS_BY_STAGE: dict[int, tuple[RequirementGroupSpec, ...]] = {
    0: (),
    1: (
        RequirementGroupSpec(
            code="NEGOTIATION_EQUALIZATION",
            stage=1,
            label="Equalização da negociação",
            message="Confirme a equalização da negociação.",
            waivable=True,
            fields=("negotiation.equalized",),
            check=lambda state: bool(state.negotiation and state.negotiation.equalized),
        ),
    ),
    2: (
        RequirementGroupSpec(
            code="COMMERCIAL_NEGOTIATION",
            stage=2,
            label="Negociação comercial",
            message="Informe a data da negociação.",
            waivable=True,
            fields=("negotiation.negotiatedAt",),
            check=lambda state: bool(
                state.negotiation and _filled(state.negotiation.negotiated_at)
            ),
        ),
    ),
    3: (
        RequirementGroupSpec(
            code="LEGAL_TICKET",
            stage=3,
            label="Chamado jurídico",
            message="Informe a data de abertura e o número do chamado jurídico.",
            waivable=True,
            fields=("legal.openedAt", "legal.ticketNumber"),
            check=lambda state: bool(
                state.legal
                and _filled(state.legal.opened_at)
                and _filled(state.legal.ticket_number)
            ),
        ),
    ),
    4: (
        RequirementGroupSpec(
            code="LEGAL_DRAFT",
            stage=4,
            label="Minuta contratual",
            message="Confirme que a minuta foi elaborada e aprovada.",
            waivable=True,
            fields=("legal.draftPrepared", "legal.draftApproved"),
            check=lambda state: bool(
                state.legal and state.legal.draft_prepared and state.legal.draft_approved
            ),
        ),
    ),
    5: (
        RequirementGroupSpec(
            code="CONTRACT",
            stage=5,
            label="Contrato",
            message=(
                "Cadastre ao menos um contrato com número, data de escrituração e "
                "arquivo no mesmo registro para avançar."
            ),
            waivable=True,
            fields=("contract.contractNumber", "contract.executedAt", "contract.file"),
            check=lambda state: _any_complete(
                state.contracts,
                lambda c: c.contract_number,
                lambda c: c.executed_at,
                lambda c: c.file_storage_key,
            ),
        ),
    ),
    6: (
        RequirementGroupSpec(
            code="PURCHASE_REQUEST",
            stage=6,
            label="SC / OCI",
            message=(
                "Cadastre ao menos uma SC/OCI com tipo, número e data no mesmo "
                "registro para avançar."
            ),
            waivable=True,
            fields=("purchaseRequest.kind", "purchaseRequest.requestNumber", "purchaseRequest.requestedAt"),
            check=lambda state: _any_complete(
                state.purchase_requests,
                lambda r: r.kind,
                lambda r: r.request_number,
                lambda r: r.requested_at,
            ),
        ),
    ),
    # `7` não existe aqui de propósito: a transição 7 -> 8 (conclusão) usa
    # `COMPLETION_GROUPS` abaixo — nenhum deles é dispensável.
}

# Etapa 7, seção 6 / Etapa 7.1 — regra de conclusão (7 -> 8): precisa estar
# efetivamente na fase 7, ter fornecedor, ter pelo menos uma OC completa (
# número + data + valor no MESMO registro) e ter o Valor Total do Projeto
# preenchido. Nenhum desses três grupos é dispensável por waiver.
COMPLETION_GROUPS: tuple[RequirementGroupSpec, ...] = (
    RequirementGroupSpec(
        code="SUPPLIER",
        stage=7,
        label="Fornecedor",
        message="Informe o fornecedor do equipamento antes de concluir.",
        waivable=False,
        fields=("equipment.supplier",),
        check=lambda state: state.has_supplier,
    ),
    RequirementGroupSpec(
        code="PURCHASE_ORDER",
        stage=7,
        label="Ordem de compra",
        message=(
            "Cadastre ao menos uma Ordem de Compra com número, data e valor no "
            "mesmo registro para concluir."
        ),
        waivable=False,
        fields=("purchaseOrder.orderNumber", "purchaseOrder.orderedAt", "purchaseOrder.amount"),
        check=lambda state: _any_complete(
            state.purchase_orders,
            lambda o: o.order_number,
            lambda o: o.ordered_at,
            lambda o: o.amount,
        ),
    ),
    RequirementGroupSpec(
        code="PROJECT_TOTAL_VALUE",
        stage=7,
        label="Valor total do projeto",
        message="Informe o Valor Total do Projeto antes de concluir.",
        waivable=False,
        fields=("equipment.projectTotalValue",),
        check=lambda state: bool(
            state.equipment and _filled(state.equipment.project_total_value)
        ),
    ),
)

_ALL_GROUPS: dict[str, RequirementGroupSpec] = {
    spec.code: spec
    for groups in (*GROUPS_BY_STAGE.values(), COMPLETION_GROUPS)
    for spec in groups
}


def groups_for(from_stage: int) -> tuple[RequirementGroupSpec, ...]:
    """Grupos de requisitos da transição `from_stage -> from_stage + 1`."""
    if from_stage == FINAL_STAGE - 1:
        return COMPLETION_GROUPS
    return GROUPS_BY_STAGE.get(from_stage, ())


def group_spec(code: str) -> RequirementGroupSpec | None:
    return _ALL_GROUPS.get(code)


def is_waivable_group(stage: int, code: str) -> bool:
    """A dispensa só é aceita quando o grupo existe, é dispensável, E
    corresponde de fato à fase informada — nunca uma string arbitrária."""
    spec = _ALL_GROUPS.get(code)
    return bool(spec and spec.waivable and spec.stage == stage)

