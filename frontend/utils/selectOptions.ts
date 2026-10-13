import type { SearchableOption } from "~/types/ui";
import { EQUIPMENT_STAGES } from "~/utils/stages";

/** Opções do `SearchableSelect` a partir de itens com `id`; o rótulo padrão é `name`. */
export function toOptions<T extends { id: string; name: string }>(
  items: readonly T[],
  label: (item: T) => string = (item) => item.name,
): SearchableOption[] {
  return items.map((item) => ({ id: item.id, label: label(item) }));
}

/** `código · nome` quando há código (contextos de projeto, nós EAP). */
export function codeNameLabel(item: { code?: string | null; name: string }): string {
  return item.code ? `${item.code} · ${item.name}` : item.name;
}

/** Etapas do workflow (0–8), na ordem do processo; o id é o índice em texto. */
export const STAGE_OPTIONS: SearchableOption[] = EQUIPMENT_STAGES.map((name, index) => ({
  id: String(index),
  label: `${index} · ${name}`,
}));
