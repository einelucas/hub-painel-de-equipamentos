"""GAP-014 — regressão contra os 41 equipamentos reais do C2 (DEV, somente
leitura). Compara o Status Negociação calculado agora (`calculate_negotiation_status`,
com `reference_date = hoje`) contra o "Status Negociação" observado no Monday
no momento da migração (`negotiation_status_observed`, staged em
`monday_import_record`).

IMPORTANTE: o valor observado é um retrato do dia em que o XLSX foi
exportado; o valor calculado usa a data de hoje. Para os estados que
dependem de "quantos dias faltam" (NO_PRAZO/PRÓXIMO/URGENTE/CRÍTICO/VENCE
HOJE/ATRASADO), uma divergência frente ao snapshot antigo é ESPERADA à
medida que o tempo passa — não é bug da fórmula. Só é reportado como
achado real quando a precedência (COMPLETED por negotiated_at) não bate,
porque essa parte não depende de data de referência nenhuma.
"""

from __future__ import annotations

import asyncio
import re
from collections import Counter

from sqlalchemy import select

from app.core.database import SessionLocal
from app.domain.equipment_calculations import NegotiationStatus
from app.models.equipment import Equipment
from app.models.monday_import import MondayImportRecord
from app.models.process import Negotiation
from app.modules.equipments.service import get_equipment_out

PCID = "b264c140-7f10-4430-93d0-d880c2029bd0"

_MONDAY_TO_ENUM = {
    "NO PRAZO": NegotiationStatus.ON_TRACK,
    "CONCLUIDO": NegotiationStatus.COMPLETED,
    "PROXIMO": NegotiationStatus.UPCOMING,
    "ATRASADO": NegotiationStatus.OVERDUE,
    "URGENTE": NegotiationStatus.URGENT,
    "CRITICO": NegotiationStatus.CRITICAL,
    "VENCE HOJE": NegotiationStatus.DUE_TODAY,
}
_DATE_DEPENDENT = {
    NegotiationStatus.ON_TRACK,
    NegotiationStatus.UPCOMING,
    NegotiationStatus.URGENT,
    NegotiationStatus.CRITICAL,
    NegotiationStatus.DUE_TODAY,
}


def _strip_emoji_and_accents(value: str) -> str:
    text = re.sub(r"[^\w\sÀ-ÿ]", "", value).strip().upper()
    replacements = {"Á": "A", "É": "E", "Í": "I", "Ó": "O", "Ú": "U", "Ã": "A", "Õ": "O", "Ç": "C"}
    for accented, plain in replacements.items():
        text = text.replace(accented, plain)
    return text


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
            record.final_entity_id: record.normalized_payload.get("negotiation_status_observed")
            for record in records
        }

        exact_match = 0
        date_dependent_diff = 0
        real_mismatch: list[tuple[str, str, str]] = []
        unmapped_observed: list[tuple[str, str]] = []
        no_observed_value = 0

        for equipment_id in equipment_ids:
            equipment = await get_equipment_out(session, equipment_id)
            calculated = equipment.calculated.negotiation_status
            observed_raw = observed_by_equipment.get(equipment_id)
            if not observed_raw:
                no_observed_value += 1
                continue
            normalized = _strip_emoji_and_accents(observed_raw)
            expected = _MONDAY_TO_ENUM.get(normalized)
            if expected is None:
                unmapped_observed.append((equipment_id, observed_raw))
                continue
            if calculated == expected:
                exact_match += 1
            elif expected in _DATE_DEPENDENT and calculated in _DATE_DEPENDENT | {NegotiationStatus.OVERDUE, NegotiationStatus.DUE_TODAY}:
                # Ambos os lados são "faltam N dias" — só o N mudou porque o
                # tempo passou entre a exportação do Monday e agora.
                date_dependent_diff += 1
            else:
                real_mismatch.append((equipment_id, expected.value, calculated.value if calculated else "None"))

        print(f"Equipamentos com negotiation_status_observed no staging: {41 - no_observed_value}/41")
        print(f"Sem valor observado (equipamento sem essa coluna preenchida): {no_observed_value}")
        print(f"Não reconhecidos após normalização: {unmapped_observed}")
        print()
        print(f"MATCH exato (mesmo enum, hoje == data da exportação em efeito): {exact_match}")
        print(
            f"Divergência esperada por passagem de tempo (categoria dependente de dias, "
            f"precedência intacta): {date_dependent_diff}"
        )
        print(f"MISMATCH real (precedência ou classificação incompatível): {len(real_mismatch)} {real_mismatch}")
        assert len(real_mismatch) == 0, "MISMATCH real encontrado — não adaptar fórmula, investigar."
        print("\nGAP-014: nenhum MISMATCH real. Fórmula e precedência batem com os dados reais do C2.")


if __name__ == "__main__":
    asyncio.run(main())
