<script setup lang="ts">
import { computed } from "vue";
import type { ApexOptions } from "apexcharts";
import type { AnalyticsStageCapex } from "~/types/dashboardAnalytics";
import { CHART_COLORS, safeNumber } from "~/utils/dashboardAnalytics";
import { formatCurrency } from "~/utils/format";

const props = defineProps<{ stages: AnalyticsStageCapex[]; loading?: boolean }>();
const informed = computed(() => props.stages.filter((stage) => stage.informed > 0));
const series = computed(() => [{ name: "CAPEX informado", data: informed.value.map((stage) => safeNumber(stage.amount)) }]);
const options = computed<ApexOptions>(() => ({
  chart: { type: "bar" },
  colors: [CHART_COLORS.primary],
  plotOptions: { bar: { horizontal: true, barHeight: "56%", borderRadius: 4 } },
  xaxis: { categories: informed.value.map((stage) => `${stage.stage}. ${stage.label}`), labels: { formatter: (value) => `R$ ${Math.round(Number(value) / 1000)} mil` } },
  yaxis: { labels: { maxWidth: 155, style: { fontSize: "10px" } } },
  dataLabels: { enabled: false },
  tooltip: { y: { formatter: (n, opts) => `${formatCurrency(n)} · ${informed.value[opts?.dataPointIndex ?? -1]?.informed ?? 0} com CAPEX` } },
  legend: { show: false },
  grid: { borderColor: CHART_COLORS.border },
}));
const height = computed(() => Math.max(265, informed.value.length * 35 + 70));
</script>

<template>
  <DashboardChartFrame
    title="CAPEX estimado por etapa"
    subtitle="Somente os equipamentos que possuem CAPEX preenchido."
    :loading="props.loading"
    :empty="!informed.length"
    note="O valor estimado não é calculado pela soma das OCs. Equipamentos sem CAPEX permanecem ausentes deste gráfico."
  >
    <ChartCanvas type="bar" :options="options" :series="series" label="CAPEX estimado informado por etapa" :height="height" />
  </DashboardChartFrame>
</template>
