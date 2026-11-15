import type {
  StartupItem, StartupItemInput, StartupMonth, StartupScenario, StartupSummary,
} from "~/types/startupSimulation";

/** UTC e strings YYYY-MM-DD evitam alterações por fuso local e horário de verão. */
function parseIso(value: string): Date | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return null;
  const [year, month, day] = value.split("-").map(Number);
  const parsed = new Date(Date.UTC(year!, month! - 1, day!));
  return parsed.getUTCFullYear() === year && parsed.getUTCMonth() === month! - 1
    && parsed.getUTCDate() === day ? parsed : null;
}

export function shiftDate(value: string | null, days: number | null): string | null {
  if (!value || days === null || !Number.isSafeInteger(days) || days < 0 || days > 36500) return null;
  const parsed = parseIso(value);
  if (!parsed) return null;
  parsed.setUTCDate(parsed.getUTCDate() - days);
  return parsed.toISOString().slice(0, 10);
}

/** Equivalência exata G=H-L, H=I-M, I=J-N. Suprimentos não participa. */
export function calculateScenarioItem(
  item: StartupItemInput, scenarioStartup: string,
): Pick<StartupItem, "deliveryDeadline" | "contractDeadline" | "negotiationDeadline"> {
  const deliveryDeadline = shiftDate(item.startupAt || scenarioStartup, item.preStartDays);
  const contractDeadline = shiftDate(deliveryDeadline, item.manufactureDays);
  const negotiationDeadline = shiftDate(contractDeadline, item.legalDays);
  return { deliveryDeadline, contractDeadline, negotiationDeadline };
}

export function summarizeScenarioRows(items: StartupItem[]): StartupSummary {
  const dates = (field: "negotiationDeadline" | "contractDeadline" | "deliveryDeadline") =>
    items.map((item) => item[field]).filter((date): date is string => Boolean(date)).sort();
  const negotiations = dates("negotiationDeadline");
  const contracts = dates("contractDeadline");
  const deliveries = dates("deliveryDeadline");
  const monthlyMap = new Map<string, StartupMonth>();
  function collect(values: string[], field: "negotiations" | "contracts" | "deliveries") {
    for (const value of values) {
      const month = value.slice(0, 7);
      const entry = monthlyMap.get(month) ?? { month, negotiations: 0, contracts: 0, deliveries: 0 };
      entry[field] += 1;
      monthlyMap.set(month, entry);
    }
  }
  collect(negotiations, "negotiations");
  collect(contracts, "contracts");
  collect(deliveries, "deliveries");
  const average = (field: "manufactureDays" | "preStartDays") => {
    const values = items.map((item) => item[field]).filter((v): v is number => v !== null);
    return values.length ? Math.round(values.reduce((a, b) => a + b, 0) / values.length * 100) / 100 : null;
  };
  return {
    equipments: items.length,
    negotiationsCalculated: negotiations.length,
    contractsCalculated: contracts.length,
    deliveriesCalculated: deliveries.length,
    firstNegotiation: negotiations[0] ?? null,
    lastNegotiation: negotiations.at(-1) ?? null,
    firstDelivery: deliveries[0] ?? null,
    lastDelivery: deliveries.at(-1) ?? null,
    averageManufactureDays: average("manufactureDays"),
    averagePreStartDays: average("preStartDays"),
    monthly: [...monthlyMap.values()].sort((a, b) => a.month.localeCompare(b.month)),
  };
}

/** Recalcula sem gravar no banco; somente o PUT persiste. */
export function previewScenario(
  scenario: StartupScenario, name: string, startupAt: string, rows: StartupItemInput[],
): StartupScenario {
  const items = rows.map((row, index) => ({
    ...row, id: scenario.items[index]?.id ?? `draft-${index}`,
    ...calculateScenarioItem(row, startupAt),
  }));
  return {
    ...scenario, name, startupAt, items, summary: summarizeScenarioRows(items),
  };
}

export function asDraftItems(scenario: StartupScenario): StartupItemInput[] {
  return scenario.items.map((item) => ({
    name: item.name, origin: item.origin, discipline: item.discipline,
    supplier: item.supplier, area: item.area, responsible: item.responsible,
    startupAt: item.startupAt, suppliesDays: item.suppliesDays,
    legalDays: item.legalDays, manufactureDays: item.manufactureDays,
    preStartDays: item.preStartDays,
  }));
}

export function formatScenarioDate(value: string | null): string {
  if (!value) return "—";
  const [y, m, d] = value.split("-");
  return `${d}/${m}/${y}`;
}

export function formatMonth(value: string): string {
  const [year, month] = value.split("-");
  return new Intl.DateTimeFormat("pt-BR", { month: "short", year: "2-digit", timeZone: "UTC" })
    .format(new Date(Date.UTC(Number(year), Number(month) - 1, 1))).replace(".", "");
}
