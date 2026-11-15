import { describe, expect, it } from "vitest";
import type { StartupMonth, StartupScenario } from "~/types/startupSimulation";
import {
  buildMonthlyComparisonRows,
  comparisonDateDelta,
  comparisonNumberDelta,
  formatAverageDays,
  formatDaysDifference,
} from "~/utils/startupComparison";
import { previewScenario } from "~/utils/startupSimulation";

const month = (value: string, negotiations: number, contracts = 0, deliveries = 0): StartupMonth => ({
  month: value, negotiations, contracts, deliveries,
});

function scenario(id: string, startupAt: string, monthly: StartupMonth[]): StartupScenario {
  return {
    id, name: id, simulationProjectId: "context", source: "MANUAL",
    createdAt: "2026-01-01T00:00:00", updatedAt: "2026-01-01T00:00:00",
    startupAt, items: [],
    summary: {
      equipments: 0,
      negotiationsCalculated: monthly.reduce((sum, row) => sum + row.negotiations, 0),
      contractsCalculated: monthly.reduce((sum, row) => sum + row.contracts, 0),
      deliveriesCalculated: monthly.reduce((sum, row) => sum + row.deliveries, 0),
      firstNegotiation: null, lastNegotiation: null,
      firstDelivery: null, lastDelivery: null,
      averageManufactureDays: null, averagePreStartDays: null,
      monthly,
    },
  };
}

describe("visão executiva do simulador", () => {
  it("compara startup de 2027 com 2028 em dias corridos e sinais corretos", () => {
    expect(comparisonDateDelta("2027-12-02", "2028-03-31")).toBe(120);
    expect(formatDaysDifference(120)).toBe("+120 dias");
    expect(formatDaysDifference(-120)).toBe("−120 dias");
    expect(formatDaysDifference(0)).toBe("0 dias");
    expect(comparisonDateDelta("2028-03-31", "2027-12-02")).toBe(-120);
  });

  it("não calcula diferença com cenário ausente ou datas inválidas", () => {
    expect(comparisonDateDelta("2027-12-02", null)).toBeNull();
    expect(comparisonDateDelta("2027-02-31", "2027-04-01")).toBeNull();
    expect(formatDaysDifference(null)).toBe("—");
    expect(formatAverageDays(null)).toBe("—");
    expect(comparisonNumberDelta(140, null)).toBeNull();
  });

  it("compara diferenças de lead time sem converter ausências em zero", () => {
    expect(formatAverageDays(134.6)).toBe("134,6 dias");
    expect(formatDaysDifference(comparisonNumberDelta(134.6, 134.6), 1)).toBe("0,0 dias");
    expect(formatDaysDifference(comparisonNumberDelta(134.6, 136.1), 1)).toBe("+1,5 dias");
    expect(formatDaysDifference(comparisonNumberDelta(136.1, 134.6), 1)).toBe("−1,5 dias");
  });

  it("alinha os meses de ambos os cenários e preserva zeros no intervalo", () => {
    const a = scenario("A", "2027-12-02", [
      month("2026-04", 1, 2, 0),
      month("2026-06", 3, 1, 1),
    ]);
    const b = scenario("B", "2028-03-31", [
      month("2026-05", 2, 0, 1),
      month("2026-08", 4, 3, 2),
    ]);
    const result = buildMonthlyComparisonRows(a, b);
    expect(result.map(row => row.month)).toEqual([
      "2026-04", "2026-05", "2026-06", "2026-07", "2026-08",
    ]);
    expect(result[0]?.a.negotiations).toBe(1);
    expect(result[0]?.b?.negotiations).toBe(0);
    expect(result[1]?.a.negotiations).toBe(0);
    expect(result[1]?.b?.negotiations).toBe(2);
    expect(result[3]?.a).toMatchObject({ negotiations: 0, contracts: 0, deliveries: 0 });
    expect(result[3]?.b).toMatchObject({ negotiations: 0, contracts: 0, deliveries: 0 });
    expect(result.reduce((sum, row) => sum + row.a.negotiations, 0)).toBe(4);
    expect(result.reduce((sum, row) => sum + (row.b?.negotiations ?? 0), 0)).toBe(6);
  });

  it("não inventa série B quando apenas o cenário A está selecionado", () => {
    const result = buildMonthlyComparisonRows(
      scenario("A", "2027-12-02", [month("2027-01", 2)]), null,
    );
    expect(result).toHaveLength(1);
    expect(result[0]?.a.negotiations).toBe(2);
    expect(result[0]?.b).toBeNull();
  });

  it("reflete alterações não salvas por meio do preview existente", () => {
    const existing = scenario("A", "2027-12-02", [month("2026-08", 1)]);
    const changed = previewScenario(existing, "Startup atualizado", "2028-03-31", []);
    const other = scenario("B", "2027-12-02", [month("2026-10", 2)]);
    expect(comparisonDateDelta(other.startupAt, changed.startupAt)).toBe(120);
    expect(buildMonthlyComparisonRows(changed, other).map(row => row.month)).toEqual(["2026-10"]);
    expect(changed.name).toBe("Startup atualizado");
  });
});
