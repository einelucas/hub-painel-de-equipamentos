"""GAP-014 (Etapa 6C) — fórmula oficial de Status Negociação.

Tabela oficial:
    < 0      ATRASADO   (OVERDUE)
    0        VENCE HOJE (DUE_TODAY)
    1-7      CRÍTICO    (CRITICAL)
    8-15     URGENTE    (URGENT)
    16-30    PRÓXIMO    (UPCOMING)
    > 30     NO PRAZO   (ON_TRACK)

Precedência (nunca reordenar): operational_status especial > negotiated_at
preenchido > negotiation_deadline ausente > tabela de dias.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.domain.equipment_calculations import NegotiationStatus, calculate_negotiation_status

_REFERENCE = date(2026, 9, 21)


@pytest.mark.parametrize(
    ("days_remaining", "expected"),
    [
        (-1, NegotiationStatus.OVERDUE),
        (0, NegotiationStatus.DUE_TODAY),
        (1, NegotiationStatus.CRITICAL),
        (7, NegotiationStatus.CRITICAL),
        (8, NegotiationStatus.URGENT),
        (15, NegotiationStatus.URGENT),
        (16, NegotiationStatus.UPCOMING),
        (30, NegotiationStatus.UPCOMING),
        (31, NegotiationStatus.ON_TRACK),
    ],
)
def test_official_threshold_table(days_remaining: int, expected: NegotiationStatus) -> None:
    deadline = date.fromordinal(_REFERENCE.toordinal() + days_remaining)
    result = calculate_negotiation_status(
        negotiation_deadline=deadline, negotiated_at=None, reference_date=_REFERENCE
    )
    assert result == expected


def test_far_overdue_is_still_overdue() -> None:
    result = calculate_negotiation_status(
        negotiation_deadline=date.fromordinal(_REFERENCE.toordinal() - 67),
        negotiated_at=None,
        reference_date=_REFERENCE,
    )
    assert result == NegotiationStatus.OVERDUE


def test_negotiated_at_present_means_completed_even_if_deadline_passed() -> None:
    """Precedência: negotiatedAt > negotiationDeadline, mesmo atrasado."""
    result = calculate_negotiation_status(
        negotiation_deadline=date.fromordinal(_REFERENCE.toordinal() - 67),
        negotiated_at=date(2026, 8, 1),
        reference_date=_REFERENCE,
    )
    assert result == NegotiationStatus.COMPLETED


def test_negotiated_at_present_means_completed_even_without_deadline() -> None:
    result = calculate_negotiation_status(
        negotiation_deadline=None, negotiated_at=date(2026, 8, 1), reference_date=_REFERENCE
    )
    assert result == NegotiationStatus.COMPLETED


def test_deadline_absent_and_not_negotiated_is_null() -> None:
    result = calculate_negotiation_status(
        negotiation_deadline=None, negotiated_at=None, reference_date=_REFERENCE
    )
    assert result is None


@pytest.mark.parametrize(
    "operational_status",
    ["CANCELADO", "cancelado", "⚠️Em Saneamento", "Em Saneamento", "Não se Aplica", "nao se aplica"],
)
def test_special_operational_statuses_are_not_applicable(operational_status: str) -> None:
    result = calculate_negotiation_status(
        negotiation_deadline=date.fromordinal(_REFERENCE.toordinal() + 5),
        negotiated_at=None,
        reference_date=_REFERENCE,
        operational_status=operational_status,
    )
    assert result == NegotiationStatus.NOT_APPLICABLE


def test_precedence_special_status_beats_negotiated_at() -> None:
    """Precedência: estados especiais do A.Status > negotiatedAt preenchido."""
    result = calculate_negotiation_status(
        negotiation_deadline=date(2026, 9, 10),
        negotiated_at=date(2026, 8, 1),
        reference_date=_REFERENCE,
        operational_status="CANCELADO",
    )
    assert result == NegotiationStatus.NOT_APPLICABLE


def test_precedence_full_order_documented_by_four_scenarios() -> None:
    """As quatro prioridades da regra, na ordem oficial, todas via a mesma
    chamada variando só o que precisa variar — prova que a ordem de checagem
    é 1) operational_status, 2) negotiated_at, 3) deadline ausente, 4) dias."""
    base = {
        "negotiation_deadline": date.fromordinal(_REFERENCE.toordinal() - 5),  # já atrasado
        "reference_date": _REFERENCE,
    }

    # Prioridade 1 vence tudo, mesmo com negotiated_at preenchido e deadline atrasado.
    assert (
        calculate_negotiation_status(
            **base, negotiated_at=date(2026, 8, 1), operational_status="Não se Aplica"
        )
        == NegotiationStatus.NOT_APPLICABLE
    )

    # Sem status especial, prioridade 2 (negotiated_at) vence o deadline atrasado.
    assert (
        calculate_negotiation_status(**base, negotiated_at=date(2026, 8, 1))
        == NegotiationStatus.COMPLETED
    )

    # Sem status especial nem negotiated_at, prioridade 3: deadline ausente -> None.
    assert (
        calculate_negotiation_status(
            negotiation_deadline=None, negotiated_at=None, reference_date=_REFERENCE
        )
        is None
    )

    # Só então a prioridade 4 (tabela de dias) decide.
    assert calculate_negotiation_status(**base, negotiated_at=None) == NegotiationStatus.OVERDUE


def test_operational_status_none_is_not_special_cased() -> None:
    """`operational_status=None` (caso real do C2 hoje) não deve ser tratado
    como um valor especial — só cai na tabela normal."""
    result = calculate_negotiation_status(
        negotiation_deadline=date.fromordinal(_REFERENCE.toordinal() + 5),
        negotiated_at=None,
        reference_date=_REFERENCE,
        operational_status=None,
    )
    assert result == NegotiationStatus.CRITICAL


def test_unrecognized_operational_status_falls_through_to_normal_table() -> None:
    """Um A.Status qualquer, fora do conjunto especial, não é tratado como
    NOT_APPLICABLE — só os 3 valores documentados disparam essa regra."""
    result = calculate_negotiation_status(
        negotiation_deadline=date.fromordinal(_REFERENCE.toordinal() + 5),
        negotiated_at=None,
        reference_date=_REFERENCE,
        operational_status="Em andamento",
    )
    assert result == NegotiationStatus.CRITICAL
