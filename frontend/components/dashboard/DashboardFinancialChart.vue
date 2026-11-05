<script setup lang="ts">
import { computed } from "vue";
import type { ApexOptions } from "apexcharts";
import type { AnalyticsMonthlyAmount } from "~/types/dashboardAnalytics";
import { CHART_COLORS, monthCaption, safeNumber } from "~/utils/dashboardAnalytics";
import { formatCurrency } from "~/utils/format";

const props = defineProps<{ months: AnalyticsMonthlyAmount[]; withoutDate: number; withoutAmount: number; loading?: boolean }>();
const amounts = computed(() => props.months.map((item) => safeNumber(item.amount)));
const cumulative = computed(() => { let total = 0; return amounts.value.map((amount) => { total += amount; return total; }); });
const hasAmounts = computed(() => props.months.some((item) => item.informedOrders > 0));
const series = computed(() => [
  { name: "Emitido no mês", type: "column", data: amounts.value },
  { name: "Acumulado (12 meses)", type: "line", data: cumulative.value },
]);
const options = computed<ApexOptions>(() => ({
  chart: { type: "line" },
  colors: [CHART_COLORS.secondary, CHART_COLORS.primary],
  stroke: { width: [0, 3], curve: "smooth" },
  plotOptions: { bar: { columnWidth: "48%", borderRadius: 4 } },
  dataLabels: { enabled: false },
  xaxis: { categories: props.months.map((item) => monthCaption(item.month)), labels: { style: { fontSize: "10px" } } },
  yaxis: { labels: { formatter: (n) => `R$ ${Math.round(n / 1000)} mil` } },
  tooltip: { shared: true, intersect: false, y: { formatter: (n) => formatCurrency(n) } },
  grid: { borderColor: CHART_COLORS.border },
  legend: { position: "bottom", fontSize: "11px" },
}));
</script>

<template>
  <DashboardChartFrame
    title="Valor emitido em OC · últimos 12 meses"
    subtitle="Barras mensais e linha acumulada, por data da ordem de compra."
    :loading="props.loading"
    :empty="!hasAmounts"
    :empty-text="props.months.some(item => item.orders) ? 'Há OCs no período, mas nenhum valor informado.' : 'Nenhuma OC datada com valor no período.'"
    :note="`${props.withoutDate} OC(s) emitida(s) sem data e ${props.withoutAmount} sem valor, não usadas para estimar a série financeira.`"
  >
    <ChartCanvas type="line" :options="options" :series="series" label="Valores de ordens de compra mensais e acumulados" :height="305" />
  </DashboardChartFrame>
</template>
