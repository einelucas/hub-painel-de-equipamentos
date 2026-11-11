import { describe, expect, it } from "vitest";
import type { Equipment } from "~/types/equipment";
import { buildEquipmentReport } from "~/utils/equipmentReport";
import { buildEquipmentReportHtml } from "~/utils/equipmentReportHtml";

function equipment(currentStage: number, name: string): Equipment {
  return {
    id: `eq-${currentStage}`,
    name,
    origin: null,
    startupAt: "2027-10-27",
    criticality: null,
    currentStage,
    stageName: currentStage === 1 ? "Negociação" : "Abertura do chamado",
    capexEstimated: null,
    projectContext: { id: "ctx-1", name: "Obra <C2>" },
    unit: { id: "unit-1", name: "Unidade & Teste" },
    discipline: null,
    eapNode: null,
    area: null,
    supplier: null,
    operationalStatus: "ACTIVE",
    projectTotalValue: null,
    contractualDeliveryStart: null,
    contractualDeliveryEnd: null,
    workPackage: null,
    workPackages: [],
    responsibleUser: { id: "user-1", name: "A <script>alert(1)</script>", email: "a@example.com" },
    componentsCount: 1,
    calculated: {
      maxLeadTimeDays: null,
      maxPreStartDays: null,
      maxFreightDays: null,
      deliveryDeadline: null,
      contractOrderDeadline: null,
      negotiationDeadline: "2026-11-01",
      negotiationDaysRemaining: -10,
      negotiationStatus: "OVERDUE",
      workNeedDaysRemaining: null,
      workNeedStatus: null,
    },
    createdAt: "2026-01-01",
    updatedAt: "2026-01-01",
  };
}

describe("relatório executivo HTML offline", () => {
  it("incorpora ApexCharts, logo, estilos e apenas os atrasos válidos", () => {
    const metrics = buildEquipmentReport([
      equipment(1, "Válido & atrasado"),
      equipment(3, "Não deve aparecer <script>alert(2)</script>"),
    ], new Date(2026, 10, 11));
    const html = buildEquipmentReportHtml({
      unitName: "Unidade & Teste",
      projectName: "Obra <C2>",
      generatedAt: new Date(2026, 10, 11, 10, 30),
      metrics,
      logoDataUrl: "data:image/png;base64,AAAA",
      apexChartsRuntime: "window.ApexCharts = window.ApexCharts || function ApexCharts() {};",
    });

    expect(metrics.overdue).toBe(1);
    expect(html).toContain("data:image/png;base64,AAAA");
    expect(html).toContain("new ApexCharts");
    expect(html).toContain('id="status-chart"');
    expect(html).toContain('id="pipeline-chart"');
    expect(html).toContain("connect-src 'none'");
    const parsed = new DOMParser().parseFromString(html, "text/html");
    expect(parsed.querySelectorAll("script[src]")).toHaveLength(0);
    expect(parsed.querySelectorAll("link[href]")).toHaveLength(0);
    expect(html).toContain("Válido &amp; atrasado");
    expect(html).not.toContain("Não deve aparecer");
    expect(html).toContain("A &lt;script&gt;alert(1)&lt;/script&gt;");
    expect(html).not.toContain("<script>alert(1)</script>");
  });

  it("gera um documento válido também sem equipamentos", () => {
    const metrics = buildEquipmentReport([], new Date(2026, 10, 11));
    const html = buildEquipmentReportHtml({
      unitName: "Unidade",
      projectName: "Obra",
      generatedAt: new Date(2026, 10, 11),
      metrics,
      logoDataUrl: "data:image/png;base64,AAAA",
      apexChartsRuntime: "window.ApexCharts = window.ApexCharts || function ApexCharts() {};",
    });

    expect(html).toMatch(/^<!doctype html>/);
    expect(html).toContain("Nenhum equipamento com negociação em atraso");
    expect(html).toContain('"data":[0]');
  });
});
