<script setup lang="ts">
import { computed } from "vue";
import type { ApexOptions } from "apexcharts";
import type { AnalyticsMonthlyCount } from "~/types/dashboardAnalytics";
import { CHART_COLORS, monthCaption } from "~/utils/dashboardAnalytics";

const props = defineProps<{ months: AnalyticsMonthlyCount[]; loading?: boolean }>();
const series = computed(() => [{ name: "Movimentações", data: props.months.map((item) => item.count) }]);
const options = computed<ApexOptions>(() => ({
  chart: { type: "area" },
  colors: [CHART_COLORS.primary],
  stroke: { curve: "smooth", width: 3 },
  fill: { type: "gradient", gradient: { opacityFrom: 0.3, opacityTo: 0.02 } },
  markers: { size: 3 },
  xaxis: { categories: props.months.map((item) => monthCaption(item.month)), labels: { style: { fontSize: "10px" } } },
  yaxis: { min: 0, labels: { formatter: (n) => String(Math.round(n)) } },
  dataLabels: { enabled: false },
  tooltip: { y: { formatter: (n) => `${Math.round(n)} transições registradas` } },
  grid: { borderColor: CHART_COLORS.border },
}));
</script>

<template>
  <DashboardChartFrame
    title="Movimentações do workflow"
    subtitle="Transições registradas por mês, nos últimos 12 meses."
    :loading="props.loading"
    :empty="!props.months.some(item => item.count)"
    note="Não é a evolução histórica do estoque por fase; importações podem não ter histórico completo de transições."
  >
    <ChartCanvas type="area" :options="options" :series="series" label="Transições do workflow por mês" :height="302" />
  </DashboardChartFrame>
</template>
