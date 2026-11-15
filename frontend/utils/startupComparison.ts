import type { StartupMonth, StartupScenario } from "~/types/startupSimulation";

/** Datas sem horário: diferenças de dias corridos devem ser independentes do fuso local. */
function isoDateMillis(value: string | null | undefined): number | null {
  if (!value || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return null;
  const [year, month, day] = value.split("-").map(Number);
  const timestamp = Date.UTC(year!, month! - 1, day!);
  const date = new Date(timestamp);
  if (
    date.getUTCFullYear() !== year || date.getUTCMonth() !== month! - 1
    || date.getUTCDate() !== day
  ) return null;
  return timestamp;
}

/** Sempre cenário B menos cenário A; nunca valor absoluto. */
export function comparisonDateDelta(
  first: string | null | undefined, second: string | null | undefined,
): number | null {
  const a = isoDateMillis(first);
  const b = isoDateMillis(second);
  return a === null || b === null ? null : Math.round((b - a) / 86_400_000);
}

export function comparisonNumberDelta(
  first: number | null | undefined, second: number | null | undefined,
): number | null {
  if (first == null || second == null || !Number.isFinite(first) || !Number.isFinite(second)) {
    return null;
  }
  return Math.round((second - first) * 100) / 100;
}

export function formatDaysDifference(value: number | null, digits = 0): string {
  if (value === null || !Number.isFinite(value)) return "—";
  const rounded = Number(value.toFixed(digits));
  const formatted = Math.abs(rounded).toLocaleString("pt-BR", {
    minimumFractionDigits: digits, maximumFractionDigits: digits,
  });
  return `${rounded > 0 ? "+" : rounded < 0 ? "−" : ""}${formatted} ${Math.abs(rounded) === 1 ? "dia" : "dias"}`;
}

export function formatAverageDays(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "—";
  return `${value.toLocaleString("pt-BR", {
    minimumFractionDigits: 1, maximumFractionDigits: 1,
  })} dias`;
}

export type MonthlyComparisonRow = {
  month: string;
  a: StartupMonth;
  b: StartupMonth | null;
};

const emptyMonth = (month: string): StartupMonth => ({
  month, negotiations: 0, contracts: 0, deliveries: 0,
});

/**
 * União cronológica de todos os meses de ambos os cenários, incluindo meses com zero.
 * Se B não foi escolhido, não exibimos uma série fictícia zerada: exibimos ausência.
 */
export function buildMonthlyComparisonRows(
  first: StartupScenario | null, second: StartupScenario | null,
): MonthlyComparisonRow[] {
  const entries = [...(first?.summary.monthly ?? []), ...(second?.summary.monthly ?? [])]
    .map(entry => entry.month)
    .filter(month => /^\d{4}-(0[1-9]|1[0-2])$/.test(month))
    .sort();
  if (!first || !entries.length) return [];

  const firstMonth = entries[0]!;
  const lastMonth = entries[entries.length - 1]!;
  const a = new Map(first.summary.monthly.map(entry => [entry.month, entry]));
  const b = new Map(second?.summary.monthly.map(entry => [entry.month, entry]) ?? []);
  const rows: MonthlyComparisonRow[] = [];

  let year = Number(firstMonth.slice(0, 4));
  let month = Number(firstMonth.slice(5, 7));
  const endYear = Number(lastMonth.slice(0, 4));
  const endMonth = Number(lastMonth.slice(5, 7));

  while ((year < endYear || (year === endYear && month <= endMonth)) && rows.length < 600) {
    const key = `${year}-${String(month).padStart(2, "0")}`;
    rows.push({ month: key, a: a.get(key) ?? emptyMonth(key),
      b: second ? b.get(key) ?? emptyMonth(key) : null });
    month += 1;
    if (month === 13) { month = 1; year += 1; }
  }

  return rows;
}
