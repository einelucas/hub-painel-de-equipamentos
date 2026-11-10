import { flushPromises, mount } from "@vue/test-utils";
import { defineComponent, h } from "vue";
import { beforeEach, describe, expect, it, vi } from "vitest";
import EquipmentExecutiveReport from "~/components/equipment/EquipmentExecutiveReport.vue";
import type { Equipment } from "~/types/equipment";

const equipment: Equipment = {
  id: "eq-1",
  name: "Caldeira de Biomassa",
  origin: "Nacional",
  startupAt: "2027-10-27",
  criticality: "Médio",
  currentStage: 3,
  stageName: "Abertura de Chamado",
  capexEstimated: null,
  projectContext: { id: "ctx-1", name: "Caldeira 4" },
  unit: { id: "unit-1", name: "Nova Mutum" },
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
  responsibleUser: null,
  componentsCount: 2,
  calculated: {
    maxLeadTimeDays: null,
    maxPreStartDays: null,
    maxFreightDays: null,
    deliveryDeadline: null,
    contractOrderDeadline: null,
    negotiationDeadline: "2026-10-01",
    negotiationDaysRemaining: -40,
    negotiationStatus: "OVERDUE",
    workNeedDaysRemaining: null,
    workNeedStatus: null,
  },
  createdAt: "2026-10-01T00:00:00Z",
  updatedAt: "2026-11-01T00:00:00Z",
};

const AppModalStub = defineComponent({
  name: "AppModal",
  setup(_, { slots }) {
    return () => h("div", { class: "app-modal-stub" }, slots.default?.());
  },
});

const ChartCanvasStub = defineComponent({
  name: "ChartCanvas",
  props: {
    type: { type: String, required: true },
    options: { type: Object, required: true },
    series: { type: Array, required: true },
    height: { type: Number, required: true },
    label: { type: String, required: true },
  },
  setup() {
    return () => h("div", { class: "chart-canvas-stub" });
  },
});

describe("EquipmentExecutiveReport", () => {
  beforeEach(() => {
    vi.stubGlobal("useApi", () => ({
      get: vi.fn().mockResolvedValue({
        items: [equipment],
        pagination: { page: 1, pageSize: 100, total: 1, totalPages: 1 },
      }),
    }));
  });

  it("renders the report with Vuetify pages, Apex series and the Inpasa logo", async () => {
    const wrapper = mount(EquipmentExecutiveReport, {
      props: {
        unitId: "unit-1",
        projectContextId: "ctx-1",
        unitName: "Nova Mutum",
        projectName: "Caldeira 4",
      },
      global: {
        components: { AppModal: AppModalStub, ChartCanvas: ChartCanvasStub },
      },
    });
    await flushPromises();

    expect(wrapper.findAll(".report-page")).toHaveLength(2);
    expect(wrapper.findAll("img.paper-logo")).toHaveLength(2);
    expect(
      wrapper.findAll("img.paper-logo").every((logo) => logo.attributes("src") === "/brand/logo-inpasa.png"),
    ).toBe(true);
    const charts = wrapper.findAllComponents(ChartCanvasStub);
    expect(charts.map((chart) => chart.props("type"))).toEqual(["bar", "bar"]);
    expect(charts[0]?.props("series")).toEqual([
      { name: "Concluído", data: [0] },
      { name: "No prazo", data: [0] },
      { name: "Atrasado", data: [1] },
      { name: "Sem classificação", data: [0] },
    ]);
    expect(charts[1]?.props("series")).toEqual([
      { name: "Equipamentos", data: [1, 0, 0, 0, 0, 0] },
    ]);
    const text = wrapper.text();
    expect(text).toContain("Resumo executivo");
    expect(text).toContain("Situação das negociações");
    expect(text).toContain("PRÓXIMO STARTUP CADASTRADO");
    expect(text).toContain("Principais pontos de atenção");
    expect(text).toContain("Equipamentos em atraso na negociação");
    expect(text).toContain("Caldeira de Biomassa");
    expect(text).toContain("Abertura de Chamado");
    expect(text).toContain("Pipeline de aquisição");
    expect(text).toContain("Os equipamentos que já concluíram a negociação seguem o fluxo normal de aquisição");
  });
});
