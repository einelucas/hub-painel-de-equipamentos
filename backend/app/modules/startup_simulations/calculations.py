"""Equações da planilha LEM F2: I=J-N, H=I-M, G=H-L; dias corridos."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta
from statistics import mean


@dataclass(frozen=True)
class ScenarioDates:
    delivery: date | None
    contract: date | None
    negotiation: date | None


def calculate_dates(
    startup: date | None,
    pre_start_days: int | None,
    manufacture_days: int | None,
    legal_days: int | None,
) -> ScenarioDates:
    """Supplies_days não participa da fórmula original; nunca somar implicitamente."""
    delivery = startup - timedelta(days=pre_start_days) if startup and pre_start_days is not None else None
    contract = (
        delivery - timedelta(days=manufacture_days)
        if delivery is not None and manufacture_days is not None else None
    )
    negotiation = (
        contract - timedelta(days=legal_days)
        if contract is not None and legal_days is not None else None
    )
    return ScenarioDates(delivery=delivery, contract=contract, negotiation=negotiation)


def summarize(rows: list[dict]) -> dict:
    """Indicadores derivados das linhas, incluindo eventos fora do intervalo do Excel."""
    def dates(key: str) -> list[date]:
        return [row[key] for row in rows if row[key] is not None]

    def avg(key: str) -> float | None:
        values = [row[key] for row in rows if row[key] is not None]
        return round(mean(values), 2) if values else None

    negotiation = dates("negotiation_deadline")
    contract = dates("contract_deadline")
    delivery = dates("delivery_deadline")
    monthly: dict[str, Counter[str]] = {
        key: Counter(value.strftime("%Y-%m") for value in values)
        for key, values in (
            ("negotiation", negotiation), ("contract", contract), ("delivery", delivery)
        )
    }
    months = sorted(set().union(*(set(counts) for counts in monthly.values())))
    return {
        "equipments": len(rows),
        "negotiations_calculated": len(negotiation),
        "contracts_calculated": len(contract),
        "deliveries_calculated": len(delivery),
        "first_negotiation": min(negotiation, default=None),
        "last_negotiation": max(negotiation, default=None),
        "first_delivery": min(delivery, default=None),
        "last_delivery": max(delivery, default=None),
        "average_manufacture_days": avg("manufacture_days"),
        "average_pre_start_days": avg("pre_start_days"),
        "monthly": [
            {"month": month, "negotiations": monthly["negotiation"][month],
             "contracts": monthly["contract"][month], "deliveries": monthly["delivery"][month]}
            for month in months
        ],
    }
