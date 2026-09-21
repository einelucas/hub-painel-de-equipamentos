import { describe, expect, it } from "vitest";
import type { DashboardSummary, StageDistribution } from "~/types/equipment";
import {
  negotiationDeadlineStatusDonut,
  negotiationProgress,
  negotiationProgressBars,
  situationDonut,
  stageChartPoints,
  startupLabel,
} from "~/utils/dashboard";
import { EQUIPMENT_STAGES } from "~/utils/stages";

function workflow(counts: Partial<Record<number, number>>): StageDistribution[] {
  return EQUIPMENT_STAGES.map((name, stage) => ({ stage, name, count: counts[stage] ?? 0 }));
}

function summary(overrides: Partial<DashboardSummary> = {}): DashboardSummary {
  return {
    context: { unitId: null, equipmentId: null },
    totals: {
      equipments: 0,
      components: 0,
      inProgress: 0,
      completed: 0,
      purchaseOrders: 0,
      purchaseOrderAmount: "0",
      capexEstimated: "0",
    },
    workflow: workflow({}),
    negotiation: { open: 0, completed: 0, inNegotiation: 0 },
    deadlines: {
      available: true,
      reason: null,
      total: 0,
      withDeadline: 0,
      withoutDeadline: 0,
      checkDeliveryFup: 0,
      neededToday: 0,
      lt30Days: 0,
      lt60Days: 0,
      lt90Days: 0,
      safe: 0,
    },
    negotiationDeadlineStatus: {
      total: 0,
      overdue: 0,
      urgent: 0,
      upcoming: 0,
      onTrack: 0,
      completed: 0,
      notCalculable: 0,
    },
    startup: { nextAt: null, daysRemaining: null, equipmentId: null, equipmentName: null },
    ...overrides,
  };
}

describe("stageChartPoints", () => {
  it("mantém as nove etapas na ordem do catálogo", () => {
    const points = stageChartPoints(workflow({ 0: 3, 8: 1 }));
    expect(points).toHaveLength(9);
    expect(points[0]).toEqual({ label: "0. Nova demanda", value: 3 });
    expect(points[8]).toEqual({ label: "8. Concluído", value: 1 });
  });
});

describe("situationDonut", () => {
  it("agrupa as contagens agregadas em nova demanda, em processo e concluído", () => {
    const items = situationDonut(workflow({ 0: 5, 3: 2, 6: 1, 8: 4 }));
    expect(items.map((item) => [item.label, item.value])).toEqual([
      ["Nova demanda", 5],
      ["Em processo", 3],
      ["Concluído", 4],
    ]);
  });

  it("não inventa categorias além das três do catálogo", () => {
    expect(situationDonut(workflow({}))).toHaveLength(3);
  });
});

describe("negotiationProgress", () => {
  it("calcula o percentual concluído sobre o total", () => {
    const result = negotiationProgress(summary({ negotiation: { open: 1, completed: 3, inNegotiation: 0 } }));
    expect(result).toBe(75);
  });

  it("devolve null quando não há base para calcular", () => {
    expect(negotiationProgress(summary())).toBeNull();
  });
});

describe("negotiationProgressBars", () => {
  it("calcula as 3 barras sobre o mesmo denominador de negotiationProgress (open + completed)", () => {
    const items = negotiationProgressBars({ open: 31, completed: 10, inNegotiation: 3 });
    expect(items).toEqual([
      { label: "Negociações concluídas", value: (10 / 41) * 100 },
      { label: "Em aberto", value: (31 / 41) * 100 },
      { label: "Em negociação/equalização", value: (3 / 41) * 100 },
    ]);
  });

  it("devolve lista vazia quando não há base para calcular (mesmo critério da barra única)", () => {
    expect(negotiationProgressBars({ open: 0, completed: 0, inNegotiation: 0 })).toEqual([]);
  });
});

describe("negotiationDeadlineStatusDonut", () => {
  it("traduz a agregação da API nas 5 fatias do widget, sem recalcular nada", () => {
    const items = negotiationDeadlineStatusDonut({
      total: 41,
      overdue: 1,
      urgent: 1,
      upcoming: 2,
      onTrack: 27,
      completed: 10,
      notCalculable: 0,
    });
    expect(items.map((item) => [item.label, item.value])).toEqual([
      ["Atrasado", 1],
      ["Urgente", 1],
      ["Próximo", 2],
      ["No prazo", 27],
      ["Concluído", 10],
    ]);
  });

  it("não inventa uma 6ª fatia para notCalculable", () => {
    const items = negotiationDeadlineStatusDonut({
      total: 3,
      overdue: 0,
      urgent: 0,
      upcoming: 0,
      onTrack: 0,
      completed: 0,
      notCalculable: 3,
    });
    expect(items).toHaveLength(5);
  });
});

describe("startupLabel", () => {
  it("descreve a startup futura em dias", () => {
    const result = startupLabel(
      summary({ startup: { nextAt: "2026-10-01", daysRemaining: 11, equipmentId: "e", equipmentName: "Bomba" } }),
    );
    expect(result).toBe("Em 11 dias");
  });

  it("usa singular para um dia e destaca a startup de hoje", () => {
    const base = { nextAt: "2026-09-21", equipmentId: "e", equipmentName: "Bomba" };
    expect(startupLabel(summary({ startup: { ...base, daysRemaining: 1 } }))).toBe("Em 1 dia");
    expect(startupLabel(summary({ startup: { ...base, daysRemaining: 0 } }))).toBe("Startup hoje");
  });

  it("avisa quando não há startup futura no recorte", () => {
    expect(startupLabel(summary())).toBe("Sem startup futura no recorte");
  });
});
