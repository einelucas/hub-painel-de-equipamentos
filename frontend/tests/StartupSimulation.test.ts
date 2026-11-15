import { describe, expect, it } from "vitest";
import { calculateScenarioItem, previewScenario, shiftDate, summarizeScenarioRows } from "~/utils/startupSimulation";
import type { StartupItemInput, StartupScenario } from "~/types/startupSimulation";

const item: StartupItemInput = {
  name: "Estruturas metálicas", origin: "Nacional",
  discipline: "Metal Mec.", supplier: "METASA", area: "Geral", responsible: "George Kazuki",
  startupAt: null, suppliesDays: 20, legalDays: 20, manufactureDays: 180, preStartDays: 279,
};

describe("simulador de startup (equações do Excel)", () => {
  it("reproduz as três datas da linha 3 do cenário 2027", () => {
    expect(calculateScenarioItem(item, "2027-12-02")).toEqual({
      deliveryDeadline: "2027-02-26",
      contractDeadline: "2026-08-30",
      negotiationDeadline: "2026-08-10",
    });
  });

  it("desloca todas as datas em 120 dias e mantém Suprimentos fora do cálculo", () => {
    const original = calculateScenarioItem(item, "2027-12-02");
    const shifted = calculateScenarioItem({ ...item, suppliesDays: 365 }, "2028-03-31");
    expect(shifted.deliveryDeadline).toBe("2027-06-26");
    expect(shiftDate(shifted.negotiationDeadline, 120)).toBe(original.negotiationDeadline);
  });

  it("não gera datas parciais inventadas quando falta prazo", () => {
    expect(calculateScenarioItem({ ...item, manufactureDays: null }, "2027-12-02")).toEqual({
      deliveryDeadline: "2027-02-26", contractDeadline: null, negotiationDeadline: null,
    });
  });

  it("inclui todos os meses e recalcula o mês quando muda o cenário", () => {
    const scenario = {
      id: "id", simulationProjectId: "project", source: "EXCEL",
      name: "2027", startupAt: "2027-12-02", createdAt: "", updatedAt: "",
      summary: {} as StartupScenario["summary"],
      items: [{ ...item, id: "row", ...calculateScenarioItem(item, "2027-12-02") }],
    };
    const changed = previewScenario(scenario, "2028", "2028-03-31", [item]);
    expect(changed.items[0]?.negotiationDeadline).toBe("2026-12-08");
    const summary = summarizeScenarioRows(changed.items);
    expect(summary.equipments).toBe(1);
    expect(summary.monthly.some((month) => month.month === "2026-12" && month.negotiations === 1)).toBe(true);
  });
});
