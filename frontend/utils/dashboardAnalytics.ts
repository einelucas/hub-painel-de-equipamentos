import type { AnalyticsDistributionItem, AnalyticsEapRisk, AnalyticsEapStage } from "~/types/dashboardAnalytics";

export const CHART_COLORS = {
  primary: "#304f7e",
  secondary: "#748dab",
  safe: "#609346",
  warning: "#d3a24d",
  critical: "#c96a6a",
  muted: "#a3adbb",
  border: "#e9eef4",
} as const;

export const FONT_FAMILY = "'Manrope', system-ui, sans-serif";

export function safeNumber(value: string | number | null | undefined): number {
  const n = Number(value);
  return Number.isFinite(n) ? n : 0;
}

export function shortEapLabel(label: string): string {
  if (label === "Sem EAP") return label;
  return label.split(" · ")[0] ?? label;
}

/** Nome da EAP sem o código, que já aparece no badge compacto. */
export function eapNameLabel(label: string): string {
  const parts = label.split(" · ");
  return parts.length > 1 ? parts.slice(1).join(" · ") : label;
}

export function monthCaption(month: string): string {
  const match = /^(\d{4})-(\d{2})$/.exec(month);
  return match ? `${match[2]}/${match[1]?.slice(-2)}` : month;
}

export function visibleTop<T>(items: T[], limit = 12): { visible: T[]; omitted: number } {
  return { visible: items.slice(0, limit), omitted: Math.max(0, items.length - limit) };
}

export function hasEapStageData(items: AnalyticsEapStage[]): boolean {
  return items.some((item) => item.total > 0);
}

export function hasRiskData(items: AnalyticsEapRisk[]): boolean {
  return items.some((item) => item.critical + item.warning + item.safe > 0);
}

export function hasDistributionData(items: AnalyticsDistributionItem[]): boolean {
  return items.some((item) => item.count > 0);
}

/** Datas do backend são date-only: converter explicitamente para UTC evita shifts de fuso. */
export function dateUtc(value: string): number {
  const time = Date.parse(`${value}T00:00:00Z`);
  return Number.isFinite(time) ? time : 0;
}

/** RangeBar representa dias inclusivos; fim exclusivo no início do dia seguinte. */
export function inclusiveRange(startAt: string, endAt: string): [number, number] {
  return [dateUtc(startAt), dateUtc(endAt) + 24 * 60 * 60 * 1000];
}
