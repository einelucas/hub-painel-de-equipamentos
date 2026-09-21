import type { EngineeringRow } from "~/types/equipment";

export interface ResponsibleGroup {
  key: string;
  label: string;
  rows: EngineeringRow[];
}

export const NO_RESPONSIBLE_KEY = "__none__";

/**
 * Agrupamento puramente de apresentação (GAP-011): derivado de
 * `row.responsibleUser` a cada carga da fila. Não persiste nada — se o
 * responsável de um equipamento mudar, o próximo `load()` da fila já
 * recalcula o grupo certo. Equipamentos sem responsável caem em "Sem
 * responsável", sempre ao final.
 */
export function groupByResponsible(rows: EngineeringRow[]): ResponsibleGroup[] {
  const groups = new Map<string, ResponsibleGroup>();
  for (const row of rows) {
    const key = row.responsibleUser?.id ?? NO_RESPONSIBLE_KEY;
    const label = row.responsibleUser?.name ?? "Sem responsável";
    if (!groups.has(key)) groups.set(key, { key, label, rows: [] });
    groups.get(key)!.rows.push(row);
  }
  return [...groups.values()].sort((a, b) => {
    if (a.key === NO_RESPONSIBLE_KEY) return 1;
    if (b.key === NO_RESPONSIBLE_KEY) return -1;
    return a.label.localeCompare(b.label);
  });
}
