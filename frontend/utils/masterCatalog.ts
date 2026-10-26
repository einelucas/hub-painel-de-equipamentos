import type { MasterArea, MasterEquipment } from "~/types/masterCatalog";

export function buildAreaMap(areas: MasterArea[]): Map<string, MasterArea> {
  return new Map(areas.map((area) => [area.id, area]));
}

export function activeRealAreas(areas: MasterArea[]): MasterArea[] {
  return areas.filter((area) => area.active && !area.isUnassigned);
}

export function findUnassignedArea(areas: MasterArea[]): MasterArea | null {
  return areas.find((area) => area.isUnassigned) ?? null;
}

export function areaNames(equipment: MasterEquipment, areaMap: Map<string, MasterArea>): string[] {
  return equipment.areaIds
    .map((id) => areaMap.get(id)?.name)
    .filter((name): name is string => Boolean(name));
}

export function areaSummary(equipment: MasterEquipment, areaMap: Map<string, MasterArea>): string {
  const names = areaNames(equipment, areaMap);
  if (!names.length) return "Sem área definida";
  if (names.length === 1) return names[0]!;
  return `${names[0]!} +${names.length - 1}`;
}

export function fullAreaSummary(
  equipment: MasterEquipment,
  areaMap: Map<string, MasterArea>,
): string {
  return areaNames(equipment, areaMap).join(" · ") || "Sem área definida";
}

export function areaUsage(area: MasterArea, equipments: MasterEquipment[]): string {
  if (area.isUnassigned) return "Categoria de sistema para modelos não classificados";
  const count = equipments.filter((item) => item.areaIds.includes(area.id)).length;
  if (!count) return "Nenhum equipamento vinculado";
  return count === 1 ? "1 equipamento vinculado" : `${count} equipamentos vinculados`;
}

export function equipmentMatchesFilter(
  equipment: MasterEquipment,
  term: string,
  areaFilter: string,
  areaMap: Map<string, MasterArea>,
): boolean {
  const matchesArea =
    !areaFilter ||
    (areaFilter === "unassigned"
      ? !equipment.areaIds.length ||
        equipment.areaIds.some((id) => areaMap.get(id)?.isUnassigned)
      : equipment.areaIds.includes(areaFilter));
  if (!matchesArea) return false;
  if (!term) return true;
  return equipment.name.toLocaleLowerCase("pt-BR").includes(term);
}

export function filterEquipments(
  equipments: MasterEquipment[],
  areas: MasterArea[],
  search: string,
  areaFilter: string,
): MasterEquipment[] {
  const term = search.trim().toLocaleLowerCase("pt-BR");
  const areaMap = buildAreaMap(areas);
  return equipments.filter((equipment) =>
    equipmentMatchesFilter(equipment, term, areaFilter, areaMap),
  );
}

export function isAreaDraftDirty(equipment: MasterEquipment, draft: string[]): boolean {
  const current = [...equipment.areaIds].sort();
  const next = [...draft].sort();
  return current.length !== next.length || current.some((id, index) => id !== next[index]);
}

export function inactiveLinkedAreas(
  equipment: MasterEquipment,
  areaMap: Map<string, MasterArea>,
): MasterArea[] {
  return equipment.areaIds
    .map((id) => areaMap.get(id))
    .filter((area): area is MasterArea => Boolean(area && !area.active));
}

export function plural(count: number, singular: string, pluralForm: string): string {
  return `${count} ${count === 1 ? singular : pluralForm}`;
}

export function componentCountLabel(count: number): string {
  return plural(count, "componente", "componentes");
}
