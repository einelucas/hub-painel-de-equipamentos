<script setup lang="ts">
import { computed } from "vue";
import type { ApexOptions } from "apexcharts";
import type { AnalyticsEapStage } from "~/types/dashboardAnalytics";
import { useEapAxisBadges } from "~/composables/useEapAxisBadges";
import { FONT_FAMILY, visibleTop, shortEapLabel } from "~/utils/dashboardAnalytics";
import DashboardEapAxisTooltip from "~/components/dashboard/DashboardEapAxisTooltip.vue";

const props = defineProps<{ items: AnalyticsEapStage[]; loading?: boolean }>();
const display = computed(() => visibleTop(props.items, 12));
const series = computed(() => display.value.visible.map((item) => ({
  name: shortEapLabel(item.label),
  data: Array.from({ length: 9 }, (_, stage) => ({ x: `F${stage}`, y: item.counts[stage] ?? 0 })),
})));
// Altura proporcional à quantidade de áreas: evita células esticadas quando há
// poucas linhas, mas cresce conforme mais áreas aparecem no recorte.
const height = computed(() => Math.max(120, display.value.visible.length * 34 + 60));

const { chartRoot, axisTip, chartEvents, showAxisTip, hideAxisTip } =
  useEapAxisBadges(() => display.value.visible);

const options = computed<ApexOptions>(() => ({
  chart: { type: "heatmap", events: chartEvents },
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
  // O eixo categórico do heatmap posiciona os rótulos ~9px mais perto da grade
  // que o eixo invertido do gráfico de barras horizontais; o padding extra
  // iguala o espaço entre o badge EAP e as células nos dois gráficos.
  grid: { padding: { left: 17, right: 5 } },
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
    <div ref="chartRoot" class="eap-chart" @mouseover="showAxisTip" @mouseout="hideAxisTip">
      <ChartCanvas type="heatmap" :options="options" :series="series" label="Mapa de calor de equipamentos por EAP e fase" :height="height" />
      <DashboardEapAxisTooltip :tip="axisTip" />
    </div>
  </DashboardChartFrame>
</template>

<style scoped>
.eap-chart { position: relative; }
</style>
