<script setup lang="ts">
import { computed } from "vue";
import type { ApexOptions } from "apexcharts";
import type { AnalyticsDeliveryWindow, AnalyticsStartup } from "~/types/dashboardAnalytics";
import { CHART_COLORS, inclusiveRange } from "~/utils/dashboardAnalytics";
import { formatDateOnly } from "~/utils/format";

const props = defineProps<{
  windows: AnalyticsDeliveryWindow[];
  startups: AnalyticsStartup[];
  incompleteCount: number;
  loading?: boolean;
}>();
const series = computed(() => [{
  name: "Janela de entrega",
  data: props.windows.map((item) => ({ x: item.equipmentName, y: inclusiveRange(item.startAt, item.endAt) })),
}]);
const options = computed<ApexOptions>(() => ({
  chart: { type: "rangeBar" },
  colors: [CHART_COLORS.primary],
  plotOptions: { bar: { horizontal: true, barHeight: "54%", rangeBarGroupRows: true, borderRadius: 3 } },
  xaxis: { type: "datetime", labels: { datetimeUTC: true, format: "dd/MM/yy", style: { fontSize: "10px" } } },
  yaxis: { labels: { maxWidth: 180, style: { fontSize: "10px" } } },
  dataLabels: { enabled: false },
  grid: { borderColor: CHART_COLORS.border },
  tooltip: {
    custom: ({ dataPointIndex }) => {
      const item = props.windows[dataPointIndex];
      if (!item) return "";
      // Somente strings fornecidas pela API; sem HTML dinâmico de dados do usuário.
      return `<div style="padding:9px 12px;font-size:11px">${formatDateOnly(item.startAt)} — ${formatDateOnly(item.endAt)}</div>`;
    },
  },
}));
const height = computed(() => Math.max(260, props.windows.length * 36 + 80));
</script>

<template>
  <DashboardChartFrame
    title="Cronograma de entregas e startups"
    subtitle="Janelas contratuais com início e fim conhecidos, e próximas datas de startup."
    :loading="props.loading"
    :empty="!props.windows.length && !props.startups.length"
    :note="`Exibidas até 20 janelas futuras/em andamento. ${props.incompleteCount} equipamento(s) possuem janela incompleta. As datas de startup não são inferidas das datas contratuais.`"
  >
    <ChartCanvas v-if="props.windows.length" type="rangeBar" :options="options" :series="series" label="Janelas contratuais de entrega por equipamento" :height="height" />
    <div v-else class="timeline-blank">Nenhuma janela contratual completa para desenhar o cronograma.</div>
    <div v-if="props.startups.length" class="startup-list">
      <strong>Próximas startups registradas</strong>
      <NuxtLink v-for="item in props.startups.slice(0, 5)" :key="item.equipmentId" :to="`/equipamentos/${item.equipmentId}`" class="startup-item">
        <span :title="item.equipmentName">{{ item.equipmentName }}</span><time :datetime="item.startupAt">{{ formatDateOnly(item.startupAt) }}</time>
      </NuxtLink>
    </div>
  </DashboardChartFrame>
</template>

<style scoped>
.timeline-blank { padding: 15px; color: #8291a3; font-size: 11px; }
.startup-list { display: grid; gap: 8px; margin: 6px 5px 8px; padding: 12px; border: 1px solid #e6edf5; border-radius: 10px; }
.startup-list > strong { font-size: 12px; color: #213758; }
.startup-item { display: flex; justify-content: space-between; gap: 14px; color: #45648c; font-size: 11.5px; text-decoration: none; }
.startup-item:hover { text-decoration: underline; }
.startup-item span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.startup-item time { flex: 0 0 auto; color: #7e8b9d; }
</style>
