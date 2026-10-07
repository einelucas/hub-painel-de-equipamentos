import type { Equipment, NamedRef } from "~/types/equipment";

type EquipmentLocationSource = Pick<Equipment, "eapNode" | "area">;

/**
 * Localização exibida do equipamento.
 *
 * `eapNode` é a fonte canônica. `area` permanece somente como fallback para
 * registros legados que ainda não passaram pela reconciliação EAP.
 */
export function equipmentLocation(
  equipment: EquipmentLocationSource,
): NamedRef | null {
  return equipment.eapNode ?? equipment.area;
}

export function equipmentLocationLabel(
  equipment: EquipmentLocationSource,
): string | null {
  const location = equipmentLocation(equipment);
  if (!location) return null;
  return location.code ? `${location.code} · ${location.name}` : location.name;
}
