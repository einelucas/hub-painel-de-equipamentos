"""Etapa 6C.1 — Status Necessidade da Obra (fórmula oficial do Monday).

Tabela oficial (daysRemaining = deliveryDeadline - referenceDate):
    null     -> null
    < 0      CHECK_DELIVERY_FUP
    0        NEEDED_TODAY
    1-29     LT_30_DAYS
    30-59    LT_60_DAYS
    60-89    LT_90_DAYS
    >= 90    SAFE
"""

from __future__ import annotations

from datetime import date

import pytest

from app.domain.equipment_calculations import WorkNeedStatus, calculate_work_need_status

_REFERENCE = date(2026, 9, 21)


def _deadline(days_remaining: int) -> date:
    return date.fromordinal(_REFERENCE.toordinal() + days_remaining)


def test_delivery_deadline_null_is_null() -> None:
    assert (
        calculate_work_need_status(delivery_deadline=None, reference_date=_REFERENCE) is None
    )


@pytest.mark.parametrize(
    ("days_remaining", "expected"),
    [
        (-1, WorkNeedStatus.CHECK_DELIVERY_FUP),
        (0, WorkNeedStatus.NEEDED_TODAY),
        (1, WorkNeedStatus.LT_30_DAYS),
        (29, WorkNeedStatus.LT_30_DAYS),
        (30, WorkNeedStatus.LT_60_DAYS),
        (59, WorkNeedStatus.LT_60_DAYS),
        (60, WorkNeedStatus.LT_90_DAYS),
        (89, WorkNeedStatus.LT_90_DAYS),
        (90, WorkNeedStatus.SAFE),
        (120, WorkNeedStatus.SAFE),
    ],
)
def test_official_threshold_table(days_remaining: int, expected: WorkNeedStatus) -> None:
    result = calculate_work_need_status(
        delivery_deadline=_deadline(days_remaining), reference_date=_REFERENCE
    )
    assert result == expected


def test_far_overdue_is_still_check_delivery_fup() -> None:
    result = calculate_work_need_status(delivery_deadline=_deadline(-200), reference_date=_REFERENCE)
    assert result == WorkNeedStatus.CHECK_DELIVERY_FUP


def test_uses_explicit_reference_date_not_the_clock() -> None:
    """Mesma data-limite, referências diferentes -> resultados diferentes:
    prova que a função não lê `date.today()` internamente."""
    deadline = date(2026, 10, 20)
    near = calculate_work_need_status(delivery_deadline=deadline, reference_date=date(2026, 10, 1))
    far = calculate_work_need_status(delivery_deadline=deadline, reference_date=date(2026, 1, 1))
    assert near == WorkNeedStatus.LT_30_DAYS
    assert far == WorkNeedStatus.SAFE
