"""Projeção pura before/after para a Etapa 01 (nenhuma escrita em banco).

O serviço futuro buscará os registros sob escopo/autorização, controlará suas
versões e chamará estas funções após validar as referências no catálogo.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.modules.equipments.bulk_edit_contracts import EquipmentCellChange, EquipmentFieldDiffOut


def preview_equipment_changes(
    *, equipment_id: str, current_values: Mapping[str, Any], changes: list[EquipmentCellChange]
) -> list[EquipmentFieldDiffOut]:
    """Calcula o diff de uma linha sem tocar nos dados de entrada.

    `current_values` é a leitura autorizada do equipamento, com campos canônicos
    em snake_case; cada mudança é previamente validada pelo schema.
    """
    result: list[EquipmentFieldDiffOut] = []
    for change in changes:
        if change.field not in current_values:
            raise ValueError(f"Campo ausente no snapshot autorizado: {change.field}")
        before = current_values[change.field]
        proposed: Any
        if change.field == "work_package_ids":
            if before is not None and not isinstance(before, list | tuple | set):
                raise ValueError("Snapshot inválido para Work Packages")
            existing = set(before or [])
            if change.operation == "ADD":
                proposed = sorted(existing | set(change.value or []))
            elif change.operation == "REMOVE":
                proposed = sorted(existing - set(change.value or []))
            elif change.operation == "REPLACE":
                proposed = sorted(set(change.value or []))
            else:  # CLEAR
                proposed = []
            old = sorted(existing)
        else:
            old = before
            empty = before is None or (isinstance(before, str) and not before.strip())
            if change.operation == "FILL_EMPTY" and not empty:
                result.append(
                    EquipmentFieldDiffOut(
                        equipment_id=equipment_id,
                        field=change.field,
                        previous_value=before,
                        proposed_value=before,
                        skipped_reason="ALREADY_FILLED",
                    )
                )
                continue
            proposed = None if change.operation == "CLEAR" else change.value

        result.append(
            EquipmentFieldDiffOut(
                equipment_id=equipment_id,
                field=change.field,
                previous_value=old,
                proposed_value=proposed,
                skipped_reason="UNCHANGED" if old == proposed else None,
            )
        )
    return result
