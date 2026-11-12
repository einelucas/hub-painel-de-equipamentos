import { flushPromises, mount } from "@vue/test-utils";
import { defineComponent, h } from "vue";
import { beforeEach, describe, expect, it, vi } from "vitest";
import EquipmentExecutiveReport from "~/components/equipment/EquipmentExecutiveReport.vue";
import type { Equipment } from "~/types/equipment";

vi.mock("~/utils/equipmentReportHtml", () => ({
  generateEquipmentReportHtml: vi.fn().mockResolvedValue(
    '<!doctype html><html lang="pt-BR"><body>MODELO HTML</body></html>',
  ),
  downloadEquipmentReportHtml: vi.fn(),
}));

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
    const equipments = Array.from({ length: 9 }, (_, currentStage) => ({
      ...equipment,
      id: `eq-${currentStage}`,
      name: `Equipamento etapa ${currentStage}`,
      currentStage,
      stageName: `Etapa ${currentStage}`,
    }));
    vi.stubGlobal("useApi", () => ({
      get: vi.fn().mockResolvedValue({
        items: equipments,
        pagination: { page: 1, pageSize: 100, total: 9, totalPages: 1 },
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

    expect(wrapper.find('[data-testid="report-html"]').exists()).toBe(true);
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
      { name: "Atrasado", data: [3] },
      { name: "Sem classificação", data: [6] },
    ]);
    expect(charts[1]?.props("series")).toEqual([
      { name: "Equipamentos", data: [1, 1, 1, 1, 1, 1] },
    ]);
    const text = wrapper.text();
    expect(text).toContain("Resumo executivo");
    expect(text).toContain("Situação das negociações");
    expect(text).toContain("PRÓXIMO STARTUP CADASTRADO");
    expect(text).toContain("Principais pontos de atenção");
    expect(text).toContain("Equipamentos em atraso na negociação");
    expect(text).toContain("Equipamento etapa 0");
    expect(text).toContain("Equipamento etapa 1");
    expect(text).toContain("Equipamento etapa 2");
    expect(text).not.toContain("Equipamento etapa 3");
    expect(text).not.toContain("Equipamento etapa 8");
    expect(text).toContain("Pipeline de aquisição");
    expect(text).toContain("Os equipamentos que já concluíram a negociação seguem o fluxo normal de aquisição");
  });

  it("consolida as obras selecionadas e não aplica filtro de equipamento da tela", async () => {
    const get = vi.fn().mockImplementation(
      (_path: string, query: Record<string, unknown>) => {
        const id = String(query.project_context_id);
        return Promise.resolve({
          items: [{
            ...equipment,
            id: `eq-${id}`,
            name: `Equipamento ${id}`,
            projectContext: { id, name: id === "ctx-1" ? "Obra 1" : "Obra 2" },
          }],
          pagination: { page: 1, pageSize: 100, total: 1, totalPages: 1 },
        });
      },
    );
    vi.stubGlobal("useApi", () => ({ get }));
    const wrapper = mount(EquipmentExecutiveReport, {
      props: {
        unitId: "unit-1",
        projectContextId: "ctx-1",
        projectContextIds: ["ctx-1", "ctx-2"],
        unitName: "Nova Mutum",
        projectName: "Obra 1 · Obra 2",
      },
      global: {
        components: { AppModal: AppModalStub, ChartCanvas: ChartCanvasStub },
      },
    });
    await flushPromises();
    expect(get).toHaveBeenCalledTimes(2);
    expect(get.mock.calls.map((call) => call[1].project_context_id)).toEqual(["ctx-1", "ctx-2"]);
    expect(get.mock.calls.every((call) =>
      call[1].unit_id === "unit-1" && !("equipment_id" in call[1])
    )).toBe(true);
    const charts = wrapper.findAllComponents(ChartCanvasStub);
    expect(charts[0]?.props("series")).toEqual([
      { name: "Concluído", data: [0] },
      { name: "No prazo", data: [0] },
      { name: "Atrasado", data: [0] },
      { name: "Sem classificação", data: [2] },
    ]);
    expect(wrapper.text()).toContain("Obra 1 · Obra 2");
  });

  it("alternates the report preview between PDF and the exact HTML model", async () => {
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

    const toggle = wrapper.get('[data-testid="report-preview-toggle"]');
    expect(toggle.attributes("aria-label")).toBe("Visualizar modelo HTML");
    expect(wrapper.findAll(".report-page")).toHaveLength(2);
    expect(wrapper.find("iframe.report-html-frame").exists()).toBe(false);

    await toggle.trigger("click");
    await flushPromises();
    expect(wrapper.find(".report-page").exists()).toBe(false);
    const frame = wrapper.get("iframe.report-html-frame");
    expect(frame.attributes("srcdoc")).toContain("MODELO HTML");
    expect(frame.attributes("sandbox")).toBe("allow-scripts");
    expect(toggle.attributes("aria-label")).toBe("Voltar à visualização PDF");
    expect(toggle.attributes("aria-pressed")).toBe("true");

    await toggle.trigger("click");
    await flushPromises();
    expect(wrapper.findAll(".report-page")).toHaveLength(2);
    expect(wrapper.find("iframe.report-html-frame").exists()).toBe(false);
    expect(toggle.attributes("aria-label")).toBe("Visualizar modelo HTML");
    expect(toggle.attributes("aria-pressed")).toBe("false");
  });
});
