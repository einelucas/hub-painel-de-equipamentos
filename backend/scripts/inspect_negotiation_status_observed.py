"""Somente leitura: lista os valores reais de `negotiation_status_observed`
(coluna "Status Negociação" do Monday) staged para os 41 equipamentos do C2,
para comparar contra o cálculo do GAP-014."""

from __future__ import annotations

import asyncio
from collections import Counter

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.monday_import import MondayImportRecord

PCID = "b264c140-7f10-4430-93d0-d880c2029bd0"


async def main() -> None:
    async with SessionLocal() as session:
        records = (
            await session.execute(
                select(MondayImportRecord).where(
                    MondayImportRecord.record_kind == "equipment",
                    MondayImportRecord.final_entity_type == "Equipment",
                )
            )
        ).scalars().all()
        counter: Counter[str] = Counter()
        samples: dict[str, str] = {}
        for record in records:
            value = record.normalized_payload.get("negotiation_status_observed")
            key = repr(value)
            counter[key] += 1
            samples.setdefault(key, record.final_entity_id or "")
        lines = [f"Total de registros de equipamento no staging: {len(records)}"]
        for key, count in counter.most_common():
            lines.append(f"  {key}: {count}x (ex. equipment_id={samples[key]})")
        output = "\n".join(lines)
        with open("../docs/validation/negotiation_status_observed.txt", "w", encoding="utf-8") as fh:
            fh.write(output + "\n")
        print(output.encode("ascii", "backslashreplace").decode("ascii"))


if __name__ == "__main__":
    asyncio.run(main())
