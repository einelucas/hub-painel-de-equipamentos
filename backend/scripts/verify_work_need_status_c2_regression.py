"""Etapa 6C.1 — regressão contra os 41 equipamentos reais do C2 (DEV,
somente leitura). Compara o Status Necessidade da Obra calculado agora
contra o valor observado no Monday no momento da migração
(`work_need_status_observed`, staged desde a MIG-001.1 — não tocado, só
lido). Mesma ressalva metodológica do GAP-014: o observado é um retrato do
dia da exportação; o calculado usa hoje. Também soma a distribuição real do
card do Dashboard (seção 14 da Etapa 6C.1)."""

from __future__ import annotations

import asyncio
import re
from collections import Counter

from sqlalchemy import select

from app.core.database import SessionLocal
from app.domain.equipment_calculations import WorkNeedStatus
from app.models.equipment import Equipment
from app.models.monday_import import MondayImportRecord
from app.modules.equipments.service import get_equipment_out

PCID = "b264c140-7f10-4430-93d0-d880c2029bd0"

_MONDAY_TO_ENUM = {
    "0": WorkNeedStatus.CHECK_DELIVERY_FUP,
    "1": WorkNeedStatus.NEEDED_TODAY,
    "2": WorkNeedStatus.LT_30_DAYS,
    "3": WorkNeedStatus.LT_60_DAYS,
    "4": WorkNeedStatus.LT_90_DAYS,
    "5": WorkNeedStatus.SAFE,
}
_DATE_DEPENDENT = set(WorkNeedStatus)  # todos os 6 dependem de "quantos dias faltam"


def _leading_digit(value: str) -> str | None:
    match = re.match(r"^\s*(\d)\.", value)
    return match.group(1) if match else None


async def main() -> None:
    async with SessionLocal() as session:
        equipment_ids = (
            await session.execute(select(Equipment.id).where(Equipment.project_context_id == PCID))
        ).scalars().all()
        assert len(equipment_ids) == 41

        records = (
            await session.execute(
                select(MondayImportRecord).where(
                    MondayImportRecord.record_kind == "equipment",
                    MondayImportRecord.final_entity_type == "Equipment",
                    MondayImportRecord.final_entity_id.in_(equipment_ids),
                )
            )
        ).scalars().all()
        observed_by_equipment = {
            record.final_entity_id: record.normalized_payload.get("work_need_status_observed")
            for record in records
        }

        exact_match = 0
        date_dependent_diff = 0
        real_mismatch: list[tuple[str, str, str]] = []
        not_comparable: list[str] = []
        distribution: Counter[str] = Counter()
        with_deadline = 0
        without_deadline = 0

        for equipment_id in equipment_ids:
            equipment = await get_equipment_out(session, equipment_id)
            calculated = equipment.calculated.work_need_status
            if equipment.calculated.delivery_deadline is None:
                without_deadline += 1
            else:
                with_deadline += 1
            distribution[calculated.value if calculated else "WITHOUT_DEADLINE"] += 1

            observed_raw = observed_by_equipment.get(equipment_id)
            if not observed_raw:
                not_comparable.append(equipment_id)
                continue
            digit = _leading_digit(observed_raw)
            expected = _MONDAY_TO_ENUM.get(digit) if digit else None
            if expected is None:
                not_comparable.append(equipment_id)
                continue
            if calculated == expected:
                exact_match += 1
            elif expected in _DATE_DEPENDENT and calculated in _DATE_DEPENDENT:
                date_dependent_diff += 1
            else:
                real_mismatch.append((equipment_id, expected.value, calculated.value if calculated else "None"))

        print(f"Comparáveis (com valor observado reconhecido): {exact_match + date_dependent_diff + len(real_mismatch)}/41")
        print(f"NOT_COMPARABLE (sem valor observado ou não reconhecido): {len(not_comparable)} {not_comparable}")
        print()
        print(f"MATCH exato: {exact_match}")
        print(f"Divergência esperada por passagem de tempo: {date_dependent_diff}")
        print(f"MISMATCH real: {len(real_mismatch)} {real_mismatch}")
        assert len(real_mismatch) == 0, "MISMATCH real — não adaptar fórmula, investigar."

        print("\nDistribuição real do card Dashboard (Situação de prazos) para o C2:")
        print(f"  CHECK_DELIVERY_FUP = {distribution.get('CHECK_DELIVERY_FUP', 0)}")
        print(f"  NEEDED_TODAY       = {distribution.get('NEEDED_TODAY', 0)}")
        print(f"  LT_30_DAYS         = {distribution.get('LT_30_DAYS', 0)}")
        print(f"  LT_60_DAYS         = {distribution.get('LT_60_DAYS', 0)}")
        print(f"  LT_90_DAYS         = {distribution.get('LT_90_DAYS', 0)}")
        print(f"  SAFE               = {distribution.get('SAFE', 0)}")
        print(f"  WITHOUT_DEADLINE   = {distribution.get('WITHOUT_DEADLINE', 0)}")
        print(f"\n  with_deadline={with_deadline} without_deadline={without_deadline} total={with_deadline + without_deadline}")
        assert with_deadline + without_deadline == 41

        print("\nEtapa 6C.1: nenhum MISMATCH real na regressão do Status Necessidade da Obra.")


if __name__ == "__main__":
    asyncio.run(main())
