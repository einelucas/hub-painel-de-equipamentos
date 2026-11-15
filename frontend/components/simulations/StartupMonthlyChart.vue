<script setup lang="ts">
import type { ApexOptions } from "apexcharts";
import type { StartupMetric, StartupScenario } from "~/types/startupSimulation";
import { formatMonth } from "~/utils/startupSimulation";

const props = defineProps<{
  scenarios: StartupScenario[];
  metric: StartupMetric;
}>();
const emit = defineEmits<{ "select-month": [month: string] }>();
const colors = ["#304f7e", "#eaa239", "#609346", "#7897b9"];
const months = computed(() => {
  const keys = props.scenarios.flatMap((s) => s.summary.monthly.map((m) => m.month)).sort();
  if (!keys.length) return [];
  const first = keys[0]!;
  const last = keys[keys.length - 1]!;
  const result: string[] = [];
  let year = Number(first.slice(0, 4));
  let month = Number(first.slice(5, 7));
  const lastYear = Number(last.slice(0, 4));
  const lastMonth = Number(last.slice(5, 7));
  // Intervalo dinâmico completo, com meses sem eventos como zero.
  while ((year! < lastYear! || (year === lastYear && month! <= lastMonth!)) && result.length < 600) {
    result.push(`${year}-${String(month).padStart(2, "0")}`);
    month += 1;
    if (month > 12) { year += 1; month = 1; }
  }
  return result;
});
const series = computed(() => props.scenarios.map((s) => {
  const counts = new Map(s.summary.monthly.map((m) => [m.month, m[props.metric]]));
  return { name: s.name, data: months.value.map((month) => counts.get(month) ?? 0) };
}));
const options = computed<ApexOptions>(() => ({
  chart: {
    type: "line",
    animations: { enabled: true, speed: 350 },
    events: {
      dataPointSelection: (_event, _chart, opts) => {
        const month = months.value[opts.dataPointIndex];
        if (month) emit("select-month", month);
      },
      markerClick: (_event, _chart, opts) => {
        const month = months.value[opts.dataPointIndex];
        if (month) emit("select-month", month);
      },
    },
  },
  colors,
  stroke: { curve: "straight", width: 3 },
  markers: { size: 4, hover: { size: 6 }, strokeWidth: 0 },
  dataLabels: {
    enabled: months.value.length <= 12,
    style: { fontSize: "10px", fontWeight: 700, colors },
    background: { enabled: false },
    offsetY: -8,
  },
  xaxis: {
    categories: months.value.map(formatMonth),
    labels: {
      rotate: -40, hideOverlappingLabels: true,
      style: { fontSize: "10px", colors: "#7f8998" },
    },
    axisBorder: { show: true, color: "#a7b1bf" },
    axisTicks: { show: false },
  },
  yaxis: {
    min: 0,
    forceNiceScale: true,
    decimalsInFloat: 0,
    labels: { formatter: (v) => String(Math.round(v)) },
  },
  grid: { borderColor: "#e9eef4", strokeDashArray: 3 },
  legend: { position: "bottom", horizontalAlign: "center", fontSize: "11px" },
  tooltip: {
    shared: true, intersect: false,
    y: { formatter: (value) => `${Number(value)} equipamento(s)` },
  },
  noData: { text: "Nenhum prazo calculável para os cenários." },
}));
</script>

<template>
  <div class="startup-monthly-chart">
    <ChartCanvas
      type="line"
      :options="options"
      :series="series"
      :height="340"
      :label="`Prazos mensais de ${metric} por cenário; clique em um mês para filtrar os equipamentos`"
    />
  </div>
</template>

<style scoped>
.startup-monthly-chart { width: 100%; min-width: 0; }
</style>
