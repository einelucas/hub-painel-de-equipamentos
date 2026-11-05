<script setup lang="ts">
import { computed } from "vue";
import type { ApexOptions } from "apexcharts";
import { CheckCircle2 } from "lucide-vue-next";
import type { NegotiationSummary } from "~/types/equipment";
import { CHART_COLORS, FONT_FAMILY } from "~/utils/dashboardAnalytics";
import { formatNumber } from "~/utils/format";

const props = defineProps<{ negotiation: NegotiationSummary; loading?: boolean }>();
const total = computed(() => props.negotiation.completed + props.negotiation.open);
const percentage = computed(() => total.value ? (props.negotiation.completed / total.value) * 100 : 0);
const chartSeries = computed(() => [Number(percentage.value.toFixed(1))]);
const options = computed<ApexOptions>(() => ({
  chart: { type: "radialBar" },
  colors: [CHART_COLORS.safe],
  plotOptions: {
    radialBar: {
      startAngle: -110,
      endAngle: 110,
      hollow: { size: "57%" },
      track: { background: "#edf1f5", strokeWidth: "90%", margin: 4 },
      dataLabels: {
        name: { show: true, offsetY: 24, color: "#8794a5", fontSize: "11px" },
        value: { show: true, offsetY: -13, fontSize: "27px", fontWeight: 750, color: "#213758", fontFamily: FONT_FAMILY, formatter: (n) => `${Number(n).toFixed(1).replace(".", ",")}%` },
      },
    },
  },
  labels: ["concluídas"],
  stroke: { lineCap: "round" },
}));
</script>

<template>
  <DashboardCard title="Negociação" subtitle="Conclusões com data de negociação registrada." :icon="CheckCircle2" :loading="props.loading">
    <div v-if="!total" class="no-negotiations">Não há negociações neste recorte.</div>
    <template v-else>
      <ChartCanvas type="radialBar" :options="options" :series="chartSeries" label="Percentual de negociações concluídas" :height="205" />
      <div class="gauge-stats">
        <div><strong>{{ formatNumber(props.negotiation.completed, 0) }}</strong><span>Concluídas</span></div>
        <div><strong>{{ formatNumber(props.negotiation.open, 0) }}</strong><span>Em aberto</span></div>
        <div><strong>{{ formatNumber(props.negotiation.inNegotiation, 0) }}</strong><span>Nas fases 1–2</span></div>
      </div>
      <p class="gauge-note">Nas fases 1–2 é um subconjunto de “Em aberto”.</p>
    </template>
  </DashboardCard>
</template>

<style scoped>
.gauge-stats { display: grid; grid-template-columns: repeat(3,minmax(0,1fr)); gap: 7px; }
.gauge-stats > div { display: flex; flex-direction: column; align-items: center; gap: 3px; border: 1px solid #e8eef4; border-radius: 8px; padding: 9px 4px; background: #fafbfd; }
.gauge-stats strong { font-size: 17px; font-weight: 800; color: #213758; }
.gauge-stats span { font-size: 10px; color: #8290a1; text-align: center; }
.gauge-note { margin: 10px 0 0; font-size: 10px; color: #8a96a7; line-height: 1.5; text-align: center; }
.no-negotiations { min-height: 230px; display: grid; place-items: center; color: #8491a3; font-size: 12px; }
</style>
