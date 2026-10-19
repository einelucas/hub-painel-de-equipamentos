export const EQUIPMENT_STAGES = [
  "Nova demanda",
  "Negociação",
  "Equalização",
  "Abertura do chamado",
  "Aprovação da minuta",
  "Escrituração do contrato",
  "SC ou OCI",
  "Aprovação da OC",
  "Concluído",
] as const;

/**
 * Cor de cada fase do workflow (0–8), definida pelo negócio.
 *
 * As demais fases (índice fora da lista) usam o amarelo de fallback e o estado
 * "cancelado" usa vermelho — ver `stageColor`.
 */
export const STAGE_COLORS: Record<number, string> = {
  0: "#a8bde7",
  1: "#349ecd",
  2: "#fdbc64",
  3: "#936fdb",
  4: "#349970",
  5: "#ff7bf0",
  6: "#79affd",
  7: "#ff8358",
  8: "#32f491",
};

/** Amarelo para fases fora da lista oficial (0–8). */
export const STAGE_FALLBACK_COLOR = "#eab308";

/** Vermelho para equipamento cancelado. */
export const STAGE_CANCELLED_COLOR = "#dc2626";

/** Mesmo alfa usado pelos badges de disciplina/criticidade (`translucentBadgeStyle`). */
const STAGE_ALPHA = 0.25;

/** Texto único para todas as fases — mesma cor dos badges de catálogo. */
const STAGE_TEXT_COLOR = "#263b59";

/**
 * Cor da fase: a cor oficial de 0 a 8; amarelo para qualquer outra fase e
 * vermelho quando o rótulo indica cancelamento.
 */
export function stageColor(stage: number, name?: string | null): string {
  if (name && /cancelad/i.test(name)) return STAGE_CANCELLED_COLOR;
  return STAGE_COLORS[stage] ?? STAGE_FALLBACK_COLOR;
}

/** `#rrggbb` + alfa → `rgba(r, g, b, a)`. */
export function withAlpha(hex: string, alpha: number): string {
  const value = hex.replace("#", "");
  const [r, g, b] = [0, 2, 4].map((offset) => Number.parseInt(value.slice(offset, offset + 2), 16));
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

/**
 * Estilo do badge de etapa: preenchimento translúcido da cor da fase (mesma
 * abordagem dos badges de disciplina/criticidade) e texto escuro fixo.
 */
export function stageBadgeStyle(stage: number, name?: string | null): Record<string, string> {
  return {
    backgroundColor: withAlpha(stageColor(stage, name), STAGE_ALPHA),
    color: STAGE_TEXT_COLOR,
  };
}
