import type { Equipment, Unit } from "~/types/equipment";

export function initialUnit(units: Unit[], requestedUnit: string): string {
  if (units.some((unit) => unit.id === requestedUnit)) return requestedUnit;
  return units.length === 1 ? units[0]!.id : "";
}

export function compatibleEquipment(equipments: Equipment[], selectedId: string): string {
  return equipments.some((equipment) => equipment.id === selectedId) ? selectedId : "";
}

export function equipmentRequestQuery(options: {
  unitId: string;
  equipmentId: string;
  search?: string;
  page?: number;
}): Record<string, string | number> {
  const query: Record<string, string | number> = {
    page: options.page ?? 1,
    pageSize: 25,
    sortBy: "name",
  };
  if (options.unitId) query.unit_id = options.unitId;
  if (options.equipmentId) query.equipment_id = options.equipmentId;
  if (options.search?.trim()) query.search = options.search.trim();
  return query;
}
