<script setup lang="ts">
import { computed } from "vue";
import type { ApexOptions } from "apexcharts";
import type { AnalyticsEapRisk } from "~/types/dashboardAnalytics";
import { CHART_COLORS, shortEapLabel, visibleTop } from "~/utils/dashboardAnalytics";

const props = defineProps<{ items: AnalyticsEapRisk[]; loading?: boolean }>();
const display = computed(() => visibleTop(props.items, 10));
const series = computed(() => [
  { name: "Crítico", data: display.value.visible.map((item) => item.critical) },
  { name: "Atenção", data: display.value.visible.map((item) => item.warning) },
  { name: "Seguro", data: display.value.visible.map((item) => item.safe) },
  { name: "Não calculável", data: display.value.visible.map((item) => item.notCalculable) },
]);
const options = computed<ApexOptions>(() => ({
  chart: { type: "bar", stacked: true },
  colors: [CHART_COLORS.critical, CHART_COLORS.warning, CHART_COLORS.safe, CHART_COLORS.muted],
  plotOptions: { bar: { horizontal: true, barHeight: "54%", borderRadius: 3 } },
  xaxis: { categories: display.value.visible.map((item) => shortEapLabel(item.label)), labels: { formatter: (n) => String(Math.round(Number(n))) } },
  yaxis: { labels: { maxWidth: 140, style: { fontSize: "10px" } } },
  dataLabels: { enabled: false },
  legend: { show: true, position: "bottom", fontSize: "10px" },
  grid: { borderColor: CHART_COLORS.border },
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
    <ChartCanvas type="bar" :options="options" :series="series" label="Situação de prazos por EAP" :height="height" />
  </DashboardChartFrame>
</template>
