<script setup lang="ts">
import { computed } from "vue";
import type { ApexOptions } from "apexcharts";
import { Clock } from "lucide-vue-next";
import type { DeadlinesSummary } from "~/types/equipment";
import { CHART_COLORS } from "~/utils/dashboardAnalytics";
import { formatNumber } from "~/utils/format";

const props = defineProps<{ deadlines: DeadlinesSummary; loading?: boolean }>();
const risk = computed(() => props.deadlines.checkDeliveryFup + props.deadlines.neededToday + props.deadlines.lt30Days);
const warning = computed(() => props.deadlines.lt60Days + props.deadlines.lt90Days);
const calculable = computed(() => risk.value + warning.value + props.deadlines.safe);
const series = computed(() => [
  { name: "Crítico", data: [risk.value] },
  { name: "Atenção", data: [warning.value] },
  { name: "Seguro", data: [props.deadlines.safe] },
]);
const options = computed<ApexOptions>(() => ({
  chart: { type: "bar", stacked: true, stackType: "100%" },
  colors: [CHART_COLORS.critical, CHART_COLORS.warning, CHART_COLORS.safe],
  plotOptions: { bar: { horizontal: true, barHeight: "52%", borderRadius: 3 } },
  xaxis: { categories: ["Prazo"], labels: { formatter: (v) => `${Math.round(Number(v))}%` } },
  yaxis: { show: false },
  dataLabels: { enabled: true, formatter: (_v, context) => String(series.value[context.seriesIndex]?.data[0] ?? ""), style: { fontSize: "11px", fontWeight: 700 } },
  legend: { show: true, position: "bottom", fontSize: "11px" },
  grid: { show: false, padding: { left: 0, right: 10 } },
  tooltip: { y: { formatter: (v) => `${v} equipamentos` } },
}));
const rows = computed(() => [
  { label: "Acompanhar entrega", count: props.deadlines.checkDeliveryFup },
  { label: "Necessário hoje", count: props.deadlines.neededToday },
  { label: "Menos de 30 dias", count: props.deadlines.lt30Days },
  { label: "Menos de 60 dias", count: props.deadlines.lt60Days },
  { label: "Menos de 90 dias", count: props.deadlines.lt90Days },
  { label: "Prazo seguro", count: props.deadlines.safe },
]);
</script>

<template>
  <DashboardCard title="Situação de prazos" subtitle="Necessidade da obra, com classificação oficial." :icon="Clock" :loading="props.loading">
    <div v-if="!props.deadlines.available" class="empty-stack">{{ props.deadlines.reason || "Indicador ainda não calculável." }}</div>
    <div v-else-if="!calculable" class="empty-stack">Nenhum equipamento possui prazo calculável neste recorte.</div>
    <template v-else>
      <div class="risk-highlight"><strong>{{ formatNumber(calculable, 0) }}</strong><span>equipamentos com prazo calculável</span></div>
      <ChartCanvas type="bar" :options="options" :series="series" label="Distribuição percentual de risco dos prazos" :height="143" />
      <div class="risk-grid">
        <div v-for="row in rows" :key="row.label" class="risk-row">
          <span>{{ row.label }}</span><strong>{{ formatNumber(row.count, 0) }}</strong>
        </div>
      </div>
      <p class="risk-muted">Sem prazo calculável: {{ formatNumber(props.deadlines.withoutDeadline, 0) }}</p>
    </template>
  </DashboardCard>
</template>

<style scoped>
.risk-highlight { display: flex; align-items: baseline; gap: 8px; padding: 4px 0; }
.risk-highlight strong { color: #213758; font-size: 23px; font-weight: 800; }
.risk-highlight span { color: #8290a1; font-size: 11px; }
.risk-grid { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 8px 12px; margin: 3px 0 11px; }
.risk-row { display: flex; justify-content: space-between; gap: 7px; min-width: 0; font-size: 10.5px; color: #657286; }
.risk-row strong { color: #334a67; font-weight: 800; }
.risk-muted { margin: 0; padding-top: 9px; border-top: 1px solid #edf1f5; font-size: 10.5px; color: #8794a5; }
.empty-stack { min-height: 235px; display: grid; place-items: center; color: #8290a1; font-size: 12px; text-align: center; }
@media (max-width: 520px) { .risk-grid { grid-template-columns: 1fr; } }
</style>
