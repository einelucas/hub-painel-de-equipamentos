<script setup lang="ts">
import { computed } from "vue";
import type { ApexOptions } from "apexcharts";
import type { NegotiationDeadlineStatusSummary } from "~/types/equipment";
import { CHART_COLORS } from "~/utils/dashboardAnalytics";

const props = defineProps<{ summary: NegotiationDeadlineStatusSummary; loading?: boolean }>();
const points = computed(() => [
  { label: "Atrasado", value: props.summary.overdue },
  { label: "Urgente", value: props.summary.urgent },
  { label: "Próximo", value: props.summary.upcoming },
  { label: "No prazo", value: props.summary.onTrack },
  { label: "Concluído", value: props.summary.completed },
]);
const series = computed(() => [{ name: "Equipamentos", data: points.value.map((item) => item.value) }]);
const options = computed<ApexOptions>(() => ({
  chart: { type: "bar" },
  colors: [CHART_COLORS.critical, "#cc5121", CHART_COLORS.warning, CHART_COLORS.primary, CHART_COLORS.safe],
  plotOptions: { bar: { horizontal: true, distributed: true, borderRadius: 5, barHeight: "57%", dataLabels: { position: "top" } } },
  xaxis: { categories: points.value.map((item) => item.label), labels: { formatter: (v) => String(Math.round(Number(v))) } },
  yaxis: { labels: { style: { fontSize: "10px" } } },
  dataLabels: {
    enabled: true,
    formatter: (v) => String(Math.round(Number(v))),
    offsetX: 16,
    style: { fontSize: "11px", fontWeight: 700, colors: ["#000000"] },
    background: { enabled: false },
  },
  legend: { show: false },
  grid: { borderColor: CHART_COLORS.border },
}));
</script>

<template>
  <DashboardChartFrame
    title="Status dos prazos de negociação"
    subtitle="Equipamentos por faixa do prazo calculado no domínio."
    :loading="props.loading"
    :empty="!points.some(item => item.value)"
    :note="`Sem prazo calculável: ${props.summary.notCalculable} equipamento(s). Não entram nas cinco categorias.`"
  >
    <ChartCanvas type="bar" :options="options" :series="series" label="Status de prazos de negociação" :height="290" />
  </DashboardChartFrame>
</template>
