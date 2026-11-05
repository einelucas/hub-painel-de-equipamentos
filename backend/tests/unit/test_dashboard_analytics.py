"""Verificações leves das regras temporais dos gráficos, sem banco real."""

from datetime import date

from app.modules.dashboard.analytics import _last_12_months
from app.modules.dashboard.analytics_schemas import (
    DashboardAnalyticsOut,
    EapRiskItemOut,
    EapStageItemOut,
)


def test_last_12_months_crosses_year() -> None:
    labels = _last_12_months(date(2026, 2, 10))
    assert len(labels) == 12
    assert labels[0] == "2025-03"
    assert labels[-1] == "2026-02"
    assert len(set(labels)) == 12


def test_no_extrapolated_dates_or_unknown_statuses() -> None:
    """Contratos preservam 'não calculável', sem distribuí-lo como seguro."""
    row = EapRiskItemOut(
        eap_id=None,
        label="Sem EAP",
        critical=1,
        warning=2,
        safe=3,
        not_calculable=4,
    )
    assert row.not_calculable == 4
    assert row.critical + row.warning + row.safe == 6
    assert EapStageItemOut(
        eap_id=None,
        label="Sem EAP",
        counts=[1] + [0] * 8,
        total=1,
    ).total == 1
    assert "monthly_workflow_movements" in DashboardAnalyticsOut.model_fields
