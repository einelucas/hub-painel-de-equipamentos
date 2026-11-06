<script setup lang="ts">
import { computed } from "vue";
import type { ApexOptions } from "apexcharts";
import type { AnalyticsEapRisk } from "~/types/dashboardAnalytics";
import { useEapAxisBadges } from "~/composables/useEapAxisBadges";
import { CHART_COLORS, shortEapLabel, visibleTop } from "~/utils/dashboardAnalytics";
import DashboardEapAxisTooltip from "~/components/dashboard/DashboardEapAxisTooltip.vue";

const props = defineProps<{ items: AnalyticsEapRisk[]; loading?: boolean }>();
const display = computed(() => visibleTop(props.items, 10));
const series = computed(() => [
  { name: "Crítico", data: display.value.visible.map((item) => item.critical) },
  { name: "Atenção", data: display.value.visible.map((item) => item.warning) },
  { name: "Seguro", data: display.value.visible.map((item) => item.safe) },
  { name: "Não calculável", data: display.value.visible.map((item) => item.notCalculable) },
]);

const { chartRoot, axisTip, chartEvents, showAxisTip, hideAxisTip } =
  useEapAxisBadges(() => display.value.visible);

const options = computed<ApexOptions>(() => ({
  chart: { type: "bar", stacked: true, events: chartEvents },
  colors: [CHART_COLORS.critical, CHART_COLORS.warning, CHART_COLORS.safe, CHART_COLORS.muted],
  plotOptions: { bar: { horizontal: true, barHeight: "54%", borderRadius: 3 } },
  xaxis: { categories: display.value.visible.map((item) => shortEapLabel(item.label)), labels: { formatter: (n) => String(Math.round(Number(n))) } },
  yaxis: { labels: { maxWidth: 140, style: { fontSize: "10px", fontWeight: 700, colors: "#2b3e58" } } },
  dataLabels: { enabled: false },
  legend: { show: true, position: "bottom", fontSize: "10px" },
  grid: { borderColor: CHART_COLORS.border, padding: { left: 8, right: 5 } },
  tooltip: { shared: true, intersect: false, y: { formatter: (n) => `${n} equipamentos` } },
}));
const height = computed(() => Math.max(280, display.value.visible.length * 36 + 85));
</script>

<template>
  <DashboardChartFrame
    title="Riscos de entrega por EAP"
    subtitle="Classificação oficial da necessidade da obra, agrupada por localização canônica."
    :loading="props.loading"
    :empty="!props.items.length"
    :note="display.omitted ? `Top ${display.visible.length} EAPs por volume; ${display.omitted} outras não exibidas.` : 'Os equipamentos sem dados suficientes aparecem como “Não calculável”.'"
  >
    <div ref="chartRoot" class="eap-chart" @mouseover="showAxisTip" @mouseout="hideAxisTip">
      <ChartCanvas type="bar" :options="options" :series="series" label="Situação de prazos por EAP" :height="height" />
      <DashboardEapAxisTooltip :tip="axisTip" />
    </div>
  </DashboardChartFrame>
</template>

<style scoped>
.eap-chart { position: relative; }
</style>
