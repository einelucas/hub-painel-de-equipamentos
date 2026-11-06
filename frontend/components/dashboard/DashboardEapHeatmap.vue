<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import type { ApexOptions } from "apexcharts";
import type { AnalyticsEapStage } from "~/types/dashboardAnalytics";
import { FONT_FAMILY, eapNameLabel, visibleTop, shortEapLabel } from "~/utils/dashboardAnalytics";

const props = defineProps<{ items: AnalyticsEapStage[]; loading?: boolean }>();
const display = computed(() => visibleTop(props.items, 12));

/** Código exibido no badge → nome completo mostrado no balão. */
const eapNames = computed(() => {
  const names = new Map<string, string>();
  for (const item of display.value.visible) {
    names.set(shortEapLabel(item.label), eapNameLabel(item.label));
  }
  return names;
});

const series = computed(() => display.value.visible.map((item) => ({
  name: shortEapLabel(item.label),
  data: Array.from({ length: 9 }, (_, stage) => ({ x: `F${stage}`, y: item.counts[stage] ?? 0 })),
})));
const height = computed(() => Math.max(280, display.value.visible.length * 34 + 90));

const chartRoot = ref<HTMLElement | null>(null);
const axisTip = ref<{ text: string; left: number; top: number; maxWidth: number } | null>(null);
let decorateFrame = 0;
let resizeObserver: ResizeObserver | null = null;

/**
 * O ApexCharts desenha os rótulos do eixo Y como texto SVG, sem suporte a
 * badge. Desenhamos uma pílula atrás de cada código depois do render, o que
 * mantém a legenda compacta e permite revelar o nome completo no balão.
 */
function decorateYAxisLabels(): void {
  const root = chartRoot.value;
  if (!root) return;
  root.querySelectorAll("rect.eap-axis-badge").forEach((rect) => rect.remove());

  for (const label of root.querySelectorAll<SVGTextElement>("text.apexcharts-yaxis-label")) {
    // O heatmap do ApexCharts desenha o código em um <tspan>; o título nativo
    // (quando existe) é removido para não sobrepor o balão customizado.
    const code = label.querySelector("tspan")?.textContent?.trim()
      || label.getAttribute("data-eap-code")
      || "";
    const name = eapNames.value.get(code);
    if (!name) continue;

    let box: DOMRect;
    try {
      box = label.getBBox();
    } catch {
      continue; // happy-dom/jsdom não implementam getBBox
    }
    if (!box.width) continue;

    const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    rect.setAttribute("class", "eap-axis-badge");
    rect.setAttribute("x", String(box.x - 6));
    rect.setAttribute("y", String(box.y - 3));
    rect.setAttribute("width", String(box.width + 12));
    rect.setAttribute("height", String(box.height + 6));
    rect.setAttribute("rx", String((box.height + 6) / 2));
    rect.setAttribute("fill", "#eef2f7");
    label.parentNode?.insertBefore(rect, label);

    label.querySelector("title")?.remove();
    label.setAttribute("data-eap-code", code);
    label.setAttribute("data-eap-name", name);
    label.setAttribute("aria-label", name);
    rect.setAttribute("data-eap-name", name);
  }
}

/** Espera o ApexCharts concluir o desenho antes de medir os rótulos. */
function scheduleDecoration(): void {
  if (typeof window === "undefined") return;
  window.cancelAnimationFrame(decorateFrame);
  decorateFrame = window.requestAnimationFrame(() => {
    decorateFrame = window.requestAnimationFrame(decorateYAxisLabels);
  });
}

function showAxisTip(event: MouseEvent): void {
  const target = event.target as Element | null;
  const label = target?.closest("[data-eap-name]");
  const name = label?.getAttribute("data-eap-name");
  if (!label || !name || typeof window === "undefined") return;

  const box = label.getBoundingClientRect();
  const left = box.right + 10;
  axisTip.value = {
    text: name,
    left,
    top: box.top + box.height / 2,
    maxWidth: Math.min(420, Math.max(160, window.innerWidth - left - 12)),
  };
}

function hideAxisTip(event: MouseEvent): void {
  const target = event.target as Element | null;
  if (!target?.closest("[data-eap-name]")) return;
  // Trocar entre a pílula e o texto não deve piscar o balão.
  if ((event.relatedTarget as Element | null)?.closest("[data-eap-name]")) return;
  axisTip.value = null;
}

function clearAxisTip(): void {
  axisTip.value = null;
}

onMounted(() => {
  window.addEventListener("resize", scheduleDecoration);
  window.addEventListener("scroll", clearAxisTip, true);
  if (typeof ResizeObserver !== "undefined" && chartRoot.value) {
    resizeObserver = new ResizeObserver(scheduleDecoration);
    resizeObserver.observe(chartRoot.value);
  }
  if (document.fonts) void document.fonts.ready.then(scheduleDecoration);
  scheduleDecoration();
});

onBeforeUnmount(() => {
  window.removeEventListener("resize", scheduleDecoration);
  window.removeEventListener("scroll", clearAxisTip, true);
  resizeObserver?.disconnect();
  window.cancelAnimationFrame(decorateFrame);
});

const options = computed<ApexOptions>(() => ({
  chart: {
    type: "heatmap",
    events: {
      mounted: scheduleDecoration,
      updated: scheduleDecoration,
    },
  },
  plotOptions: {
    heatmap: {
      enableShades: false,
      colorScale: {
        ranges: [
          { from: 0, to: 0, color: "#f0f3f8", name: "Sem equipamentos" },
          { from: 1, to: 4, color: "#b9cee6", name: "1–4" },
          { from: 5, to: 14, color: "#7299c5", name: "5–14" },
          { from: 15, to: 999999, color: "#304f7e", name: "15+" },
        ],
      },
    },
  },
  dataLabels: { enabled: true, formatter: (v) => Number(v) ? String(v) : "", style: { fontSize: "10px", colors: ["#263b57"] } },
  xaxis: { labels: { style: { fontSize: "10px", fontFamily: FONT_FAMILY } }, title: { text: "Fases do processo 0–8" } },
  yaxis: {
    labels: {
      maxWidth: 135,
      style: { fontSize: "10px", fontFamily: FONT_FAMILY, fontWeight: 700, colors: "#2b3e58" },
    },
  },
  grid: { padding: { left: 8, right: 5 } },
  tooltip: { y: { formatter: (value) => `${value} equipamento(s)` } },
  legend: { show: false },
}));
</script>

<template>
  <DashboardChartFrame
    title="Mapa de concentração · EAP × fase"
    subtitle="Cada célula representa a quantidade de equipamentos em um nó EAP e uma fase."
    :loading="props.loading"
    :empty="!props.items.length"
    :note="display.omitted ? `Mostrando ${display.visible.length} nós com maior volume, de ${props.items.length} no recorte.` : 'Equipamentos sem EAP aparecem em linha própria e não recebem classificação automática.'"
  >
    <div ref="chartRoot" class="eap-heatmap" @mouseover="showAxisTip" @mouseout="hideAxisTip">
      <ChartCanvas type="heatmap" :options="options" :series="series" label="Mapa de calor de equipamentos por EAP e fase" :height="height" />
      <span
        v-if="axisTip"
        class="eap-axis-tip"
        role="tooltip"
        :style="{ left: `${axisTip.left}px`, top: `${axisTip.top}px`, maxWidth: `${axisTip.maxWidth}px` }"
      >{{ axisTip.text }}</span>
    </div>
  </DashboardChartFrame>
</template>

<style scoped>
.eap-heatmap { position: relative; }
.eap-axis-tip {
  position: fixed;
  z-index: 70;
  padding: 5px 10px;
  border-radius: 9px;
  background: #2b3e58;
  color: #fff;
  font-size: 11.5px;
  font-weight: 700;
  line-height: 1.45;
  white-space: pre-wrap;
  pointer-events: none;
  box-shadow: 0 6px 18px rgb(20 37 58 / 18%);
  transform: translateY(-50%);
}
.eap-axis-tip::before {
  position: absolute;
  top: 50%;
  right: 100%;
  border: 5px solid transparent;
  border-right-color: #2b3e58;
  content: "";
  transform: translateY(-50%);
}
</style>
