import { mount } from "@vue/test-utils";
import { defineComponent, h, nextTick } from "vue";
import { describe, expect, it } from "vitest";
import DashboardEapHeatmap from "~/components/dashboard/DashboardEapHeatmap.vue";

const ChartCanvasStub = defineComponent({
  name: "ChartCanvas",
  props: { type: String, options: Object, series: Array, label: String, height: Number },
  setup() {
    return () => h("div", { class: "chart-canvas-stub" });
  },
});

const DashboardChartFrameStub = defineComponent({
  name: "DashboardChartFrame",
  props: { title: String, subtitle: String, loading: Boolean, empty: Boolean, note: String },
  setup(_props, { slots }) {
    return () => h("section", { class: "chart-frame-stub" }, slots.default?.());
  },
});

const global = {
  components: {
    ChartCanvas: ChartCanvasStub,
    DashboardChartFrame: DashboardChartFrameStub,
  },
};

const items = [
  {
    eapId: "eap-1",
    label: "01.A · Caldeira",
    counts: [1, 0, 0, 0, 0, 0, 0, 0, 0],
    total: 1,
  },
];

describe("DashboardEapHeatmap", () => {
  it("revela o nome completo ao passar o mouse no badge da legenda EAP", async () => {
    const wrapper = mount(DashboardEapHeatmap, { props: { items }, global });
    const root = wrapper.get(".eap-chart").element;
    const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
    label.setAttribute("data-eap-name", "Caldeira");
    root.appendChild(label);

    label.dispatchEvent(new MouseEvent("mouseover", { bubbles: true }));
    await nextTick();
    expect(wrapper.get("[role='tooltip']").text()).toBe("Caldeira");

    label.dispatchEvent(new MouseEvent("mouseout", { bubbles: true, relatedTarget: document.body }));
    await nextTick();
    expect(wrapper.find("[role='tooltip']").exists()).toBe(false);
  });
});
