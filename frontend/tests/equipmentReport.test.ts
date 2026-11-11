import { describe, expect, it } from "vitest";
import type { Equipment } from "~/types/equipment";
import { buildEquipmentReport, chunks, formatReportDate } from "~/utils/equipmentReport";

const make = (override: Partial<Equipment> = {}): Equipment => ({
  id: "id", name: "Teste", origin: null, startupAt: null, criticality: null,
  currentStage: 0, stageName: "Nova demanda", capexEstimated: null,
  projectContext: { id: "p", name: "Fase 1" }, unit: { id: "u", name: "Rio Verde" },
  discipline: null, eapNode: null, area: null, supplier: null,
  operationalStatus: "ACTIVE", projectTotalValue: null,
  contractualDeliveryStart: null, contractualDeliveryEnd: null,
  workPackage: null, workPackages: [], responsibleUser: null, componentsCount: 2,
  calculated: {
    maxLeadTimeDays: null, maxPreStartDays: null, maxFreightDays: null,
    deliveryDeadline: null, contractOrderDeadline: null, negotiationDeadline: null,
    negotiationDaysRemaining: null, negotiationStatus: null,
    workNeedDaysRemaining: null, workNeedStatus: null,
  }, createdAt: "2026-01-01", updatedAt: "2026-01-01", ...override,
});

describe("relatório executivo da obra", () => {
  const date = new Date(2026, 10, 10);
  it("não confunde componentes com equipamentos e não inventa concluídos", () => {
    const rows = [
      make({ currentStage: 8, componentsCount: 20, calculated: { ...make().calculated, negotiationStatus: "COMPLETED" } }),
      make({ currentStage: 3, calculated: { ...make().calculated, negotiationStatus: null } }),
    ];
    const data = buildEquipmentReport(rows, date);
    expect(data.total).toBe(2);
    expect(data.components).toBe(22);
    expect(data.completed).toBe(1);
    expect(data.unclassified).toBe(1);
    expect(data.pipeline.find((x) => x.stage === 3)?.count).toBe(1);
  });
  it("calcula atraso quando houver data limite e prioriza os mais atrasados", () => {
    const base = make().calculated;
    const data = buildEquipmentReport([
      make({ name: "Primeiro", calculated: { ...base, negotiationStatus: "OVERDUE", negotiationDeadline: "2026-11-01", negotiationDaysRemaining: -9 } }),
      make({ name: "Segundo", calculated: { ...base, negotiationStatus: "OVERDUE", negotiationDeadline: "2026-11-08", negotiationDaysRemaining: null } }),
    ], date);
    expect(data.overdueEquipments.map((x) => x.daysLate)).toEqual([9, 2]);
  });
  it("contabiliza OVERDUE apenas nas etapas 0, 1 e 2", () => {
    const base = make().calculated;
    const overdueByStage = Array.from({ length: 9 }, (_, currentStage) =>
      make({
        id: `stage-${currentStage}`,
        name: `Etapa ${currentStage}`,
        currentStage,
        calculated: {
          ...base,
          negotiationStatus: "OVERDUE",
          negotiationDeadline: "2026-11-01",
          negotiationDaysRemaining: -9,
        },
      }),
    );
    const onTrack = make({
      id: "on-track",
      currentStage: 1,
      calculated: { ...base, negotiationStatus: "ON_TRACK" },
    });

    const data = buildEquipmentReport([...overdueByStage, onTrack], date);

    expect(data.overdueEquipments.map((item) => item.equipment.currentStage)).toEqual([0, 1, 2]);
    expect(data.overdue).toBe(3);
    expect(data.overduePercent).toBe(30);
    expect(data.onTime).toBe(1);
    expect(data.unclassified).toBe(6);
    expect(data.unclassifiedPercent).toBe(60);
    expect(data.pipeline.map((item) => item.count)).toEqual([1, 1, 1, 1, 1, 1]);
  });
  it("considera apenas startups futuros, sem herdar startup entre componentes", () => {
    const data = buildEquipmentReport([
      make({ startupAt: "2026-11-09" }),
      make({ startupAt: "2026-11-20" }),
      make({ startupAt: "2026-11-12" }),
    ], date);
    expect(data.daysToNextStartup).toBe(2);
    expect(formatReportDate(data.nextStartup)).toBe("12/11/2026");
  });
  it("não perde linhas na divisão em páginas", () => {
    expect(chunks(Array.from({ length: 23 }, (_, i) => i), 8).map((rows) => rows.length)).toEqual([8, 8, 7]);
    expect(chunks([], 8)).toEqual([[]]);
  });
});
