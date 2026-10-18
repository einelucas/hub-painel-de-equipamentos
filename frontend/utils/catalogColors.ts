import type { NamedRef } from "~/types/equipment";

/**
 * Cinza neutro para itens de catálogo que ainda não têm cor cadastrada.
 *
 * As cores de disciplina e de criticidade são **dados do banco**, editáveis em
 * Hub → Administração: o código não define nem sugere cor por item. Este valor
 * só aparece enquanto o registro está sem cor (ex.: disciplina criada por uma
 * importação antes de alguém configurá-la).
 */
export const CATALOG_FALLBACK_COLOR = "#64748b";

/**
 * Resolve a cor de um item de catálogo.
 *
 * A cor é sempre a que está gravada no banco (`color`), já validada em
 * `#RRGGBB` na entrada da API. Sem cor cadastrada, cai no cinza neutro.
 */
export function catalogColor(color?: string | null): string {
  return color?.trim() || CATALOG_FALLBACK_COLOR;
}

/** Cor do badge de disciplina — sempre a cor cadastrada no banco. */
export function disciplineColor(discipline: NamedRef): string {
  return catalogColor(discipline.color);
}

/** Cor do badge de criticidade — sempre a cor cadastrada no banco. */
export function criticalityColor(color?: string | null): string {
  return catalogColor(color);
}

export function translucentBadgeStyle(color: string): Record<string, string> {
  return {
    "--badge-color": color,
    "--badge-background": `${color}67`,
    "--badge-border": `${color}52`,
  };
}
