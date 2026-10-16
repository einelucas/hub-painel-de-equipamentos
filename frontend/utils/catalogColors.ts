import type { NamedRef } from "~/types/equipment";

const DISCIPLINE_COLORS: Record<string, string> = {
  CIV: "#216edf",
  MEC: "#ff8358",
  MM: "#ff8358",
  "E&I": "#b0dc51",
  EI: "#b0dc51",
  ELE: "#b0dc51",
  EIA: "#b0dc51",
  AUT: "#e8697d",
  CAL: "#fdbf6b",
  PDC: "#b57de3",
  OPE: "#17b897",
  SUP: "#00a8cc",
  PRO: "#845ec2",
  MAN: "#e17055",
  QUA: "#00b894",
  LAB: "#0984e3",
  OUT: "#747d8c",
};

export function disciplineColor(discipline: NamedRef): string {
  const code = discipline.code?.trim().toUpperCase();
  return discipline.color ?? (code ? DISCIPLINE_COLORS[code] : undefined) ?? "#64748b";
}

export function criticalityColor(label: string | null | undefined, color?: string | null): string {
  if (color) return color;
  const normalized = label?.normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase() ?? "";
  if (normalized.startsWith("longo")) return "#6645a9";
  if (normalized.startsWith("medio")) return "#777ae5";
  if (normalized.startsWith("curto")) return "#79affd";
  return "#64748b";
}

export function translucentBadgeStyle(color: string): Record<string, string> {
  return {
    "--badge-color": color,
    "--badge-background": `${color}24`,
    "--badge-border": `${color}52`,
  };
}
