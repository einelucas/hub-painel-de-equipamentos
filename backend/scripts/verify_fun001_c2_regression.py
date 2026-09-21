"""FUN-001 — regressão contra os 41 equipamentos / 164 componentes reais do
C2 (DEV). Somente leitura: nada é criado, alterado ou apagado.

Para cada componente, recalcula os prazos diretamente com
`app.domain.equipment_calculations` a partir dos campos-base já no banco, e
compara contra o que `component_out`/`get_equipment_out` (a mesma função
usada pela API viva) devolveu. Também confere os agregados de cada um dos
41 equipamentos. Reporta MATCH/MISMATCH.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.database import SessionLocal
from app.domain.equipment_calculations import (
    ComponentDeadlineValues,
    ComponentSchedule,
    aggregate_component_deadlines,
    calculate_component_deadlines,
    days_until,
)
from app.models.equipment import Equipment, EquipmentComponent
from app.modules.equipments.service import component_out, get_equipment_out

PCID = "b264c140-7f10-4430-93d0-d880c2029bd0"


async def main() -> None:
    reference_date = datetime.now(UTC).date()
    async with SessionLocal() as session:
        equipment_ids = (
            await session.execute(select(Equipment.id).where(Equipment.project_context_id == PCID))
        ).scalars().all()
        assert len(equipment_ids) == 41, f"baseline quebrada: {len(equipment_ids)} equipamentos"

        component_match = 0
        component_mismatch: list[str] = []
        components_compared = 0

        equipment_match = 0
        equipment_mismatch: list[str] = []

        for equipment_id in equipment_ids:
            components = (
                await session.execute(
                    select(EquipmentComponent).where(EquipmentComponent.equipment_id == equipment_id)
                )
            ).scalars().all()

            deadline_values: list[ComponentDeadlineValues] = []
            for component in components:
                components_compared += 1
                expected = calculate_component_deadlines(
                    ComponentSchedule(
                        startup_at=component.startup_at,
                        pre_start_days=component.pre_start_days,
                        freight_days=component.freight_days,
                        lead_time_days=component.lead_time_days,
                    )
                )
                actual = component_out(component, reference_date=reference_date).calculated
                ok = (
                    expected.delivery_deadline == actual.delivery_deadline
                    and expected.collection_available_at == actual.available_for_collection
                    and expected.contract_or_po_deadline == actual.contract_order_deadline
                    and expected.negotiation_deadline == actual.negotiation_deadline
                )
                if ok:
                    component_match += 1
                else:
                    component_mismatch.append(component.id)
                deadline_values.append(
                    ComponentDeadlineValues(
                        lead_time_days=component.lead_time_days,
                        pre_start_days=component.pre_start_days,
                        freight_days=component.freight_days,
                        delivery_deadline=expected.delivery_deadline,
                        contract_or_po_deadline=expected.contract_or_po_deadline,
                        negotiation_deadline=expected.negotiation_deadline,
                    )
                )

            expected_agg = aggregate_component_deadlines(deadline_values)
            equipment_out = await get_equipment_out(session, equipment_id)
            actual_agg = equipment_out.calculated
            agg_ok = (
                expected_agg.max_lead_time_days == actual_agg.max_lead_time_days
                and expected_agg.max_pre_start_days == actual_agg.max_pre_start_days
                and expected_agg.max_freight_days == actual_agg.max_freight_days
                and expected_agg.min_delivery_deadline == actual_agg.delivery_deadline
                and expected_agg.min_contract_or_po_deadline == actual_agg.contract_order_deadline
                and expected_agg.min_negotiation_deadline == actual_agg.negotiation_deadline
            )
            expected_days_remaining = (
                days_until(expected_agg.min_negotiation_deadline, reference_date=reference_date)
                if expected_agg.min_negotiation_deadline is not None
                else None
            )
            agg_ok = agg_ok and expected_days_remaining == actual_agg.negotiation_days_remaining
            if agg_ok:
                equipment_match += 1
            else:
                equipment_mismatch.append(equipment_id)

        print(f"Componentes comparados: {components_compared} (esperado 164)")
        print(f"Componentes MATCH: {component_match}")
        print(f"Componentes MISMATCH: {len(component_mismatch)} {component_mismatch}")
        print(f"\nEquipamentos comparados: {len(equipment_ids)} (esperado 41)")
        print(f"Equipamentos MATCH: {equipment_match}")
        print(f"Equipamentos MISMATCH: {len(equipment_mismatch)} {equipment_mismatch}")

        assert components_compared == 164
        assert len(component_mismatch) == 0
        assert equipment_match == 41
        assert len(equipment_mismatch) == 0
        print("\nFUN-001: 0 MISMATCH em 164 componentes e 41 equipamentos reais do C2.")


if __name__ == "__main__":
    asyncio.run(main())
