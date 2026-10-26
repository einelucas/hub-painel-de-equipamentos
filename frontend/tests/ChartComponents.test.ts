import { mount } from "@vue/test-utils";
import { defineComponent, h } from "vue";
import { describe, expect, it } from "vitest";
import BarChart from "~/components/charts/BarChart.vue";
import DonutChart from "~/components/charts/DonutChart.vue";

const ChartCanvasStub = defineComponent({
  name: "ChartCanvas",
  props: {
    type: { type: String, required: true },
    options: { type: Object, required: true },
    series: { type: Array, required: true },
    label: { type: String, required: true },
    height: { type: Number, required: true },
  },
  setup() {
    return () => h("div", { class: "chart-canvas-stub" });
  },
});

const global = { components: { ChartCanvas: ChartCanvasStub } };

type TestChartOptions = {
  xaxis: { categories: string[] };
  yaxis: { max: number };
  dataLabels: { enabled: boolean };
  annotations?: { yaxis: Array<{ y: number }> };
  labels?: string[];
  colors?: string[];
  plotOptions?: {
    pie?: {
      donut?: {
        labels?: {
          total?: { formatter?: () => string };
        };
      };
    };
  };
};

describe("BarChart", () => {
  it("mapeia pontos, meta e sufixo para as opções do ApexCharts", () => {
    const wrapper = mount(BarChart, {
      props: {
        points: [
          { label: "Nova demanda", value: 3 },
          { label: "Em andamento", value: null },
          { label: "Concluído", value: 5 },
        ],
        target: 4,
        seriesLabel: "Equipamentos",
      },
      global,
    });

    const canvas = wrapper.findComponent(ChartCanvasStub);
    const options = canvas.props("options") as TestChartOptions;

    expect(canvas.props("type")).toBe("bar");
    expect(canvas.props("series")).toEqual([
      { name: "Equipamentos", data: [3, null, 5] },
    ]);
    expect(options.xaxis.categories).toEqual([
      "Nova demanda",
      "Em andamento",
      "Concluído",
    ]);
    expect(options.annotations?.yaxis[0]?.y).toBe(4);
    expect(options.dataLabels.enabled).toBe(true);
    expect(options.yaxis.max).toBe(6);
    expect(canvas.props("label")).toContain("Nova demanda: 3");
    expect(wrapper.text()).toContain("Meta 4");
  });

  it("omite os rótulos e a legenda quando desabilitados", () => {
    const wrapper = mount(BarChart, {
      props: {
        points: [{ label: "Etapa", value: 2 }],
        showValues: false,
        showLegend: false,
      },
      global,
    });

    const options = wrapper
      .findComponent(ChartCanvasStub)
      .props("options") as TestChartOptions;

    expect(options.dataLabels.enabled).toBe(false);
    expect(wrapper.find(".chart-legend").exists()).toBe(false);
  });
});

describe("DonutChart", () => {
  const items = [
    { label: "Nova demanda", value: 45, color: "#8697ad" },
    { label: "Em processo", value: 30, color: "#304f7e" },
    { label: "Concluído", value: 25, color: "#609346" },
  ];

  it("mapeia séries, cores e legenda com valores", () => {
    const wrapper = mount(DonutChart, {
      props: { items, showLegendValues: true },
      global,
    });

    const canvas = wrapper.findComponent(ChartCanvasStub);
    const options = canvas.props("options") as TestChartOptions;

    expect(canvas.props("type")).toBe("donut");
    expect(canvas.props("series")).toEqual([45, 30, 25]);
    expect(options.labels).toEqual([
      "Nova demanda",
      "Em processo",
      "Concluído",
    ]);
    expect(options.colors).toEqual(["#8697ad", "#304f7e", "#609346"]);
    expect(options.dataLabels.enabled).toBe(true);
    expect(
      options.plotOptions?.pie?.donut?.labels?.total?.formatter?.(),
    ).toBe("100%");
    expect(wrapper.findAll(".donut-legend-item")).toHaveLength(3);
    expect(wrapper.text()).toContain("45%");
  });

  it("mostra o estado vazio quando não há valores positivos", () => {
    const wrapper = mount(DonutChart, {
      props: {
        items: [
          { label: "Nova demanda", value: 0, color: "#8697ad" },
          { label: "Concluído", value: 0, color: "#609346" },
        ],
      },
      global,
    });

    expect(wrapper.findComponent(ChartCanvasStub).exists()).toBe(false);
    expect(wrapper.find(".donut-empty-ring").text()).toBe("Sem dados");
    expect(wrapper.findAll(".donut-legend-item")).toHaveLength(2);
  });
});
