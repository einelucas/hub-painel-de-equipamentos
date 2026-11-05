<script setup lang="ts">
import { computed } from "vue";
import type { ApexOptions } from "apexcharts";
import type { StageDistribution } from "~/types/equipment";
import { CHART_COLORS, FONT_FAMILY } from "~/utils/dashboardAnalytics";

const props = defineProps<{ workflow: StageDistribution[]; selectedStage?: number | null }>();
const emit = defineEmits<{ selectStage: [stage: number] }>();
const ordered = computed(() => [...props.workflow].sort((a, b) => a.stage - b.stage));
const series = computed(() => [{ name: "Equipamentos", data: ordered.value.map((s) => s.count) }]);
const options = computed<ApexOptions>(() => ({
  chart: {
    type: "bar",
    toolbar: { show: true },
    events: {
      dataPointSelection: (_event, _context, config) => {
        const item = ordered.value[config.dataPointIndex];
        if (item) emit("selectStage", item.stage);
      },
    },
  },
  colors: ["#008FFB"],
  plotOptions: {
    bar: {
      horizontal: true,
      barHeight: "55%",
      borderRadius: 4,
      borderRadiusApplication: "end",
      distributed: false,
      dataLabels: { position: "top" },
    },
  },
  xaxis: {
    categories: ordered.value.map((s) => `${s.stage}. ${s.name}`),
    labels: { formatter: (n) => String(Math.round(Number(n))), style: { fontSize: "10px" } },
    tickAmount: 4,
  },
  yaxis: { labels: { maxWidth: 160, style: { fontSize: "10.5px", fontFamily: FONT_FAMILY } } },
  dataLabels: {
    enabled: true,
    formatter: (value) => String(Math.round(Number(value))),
    offsetX: 16,
    style: { fontSize: "11px", fontWeight: 700, colors: ["#000000"] },
    background: { enabled: false },
  },
  grid: { borderColor: CHART_COLORS.border, padding: { top: 14, left: 8, right: 15 } },
  legend: { show: false },
  tooltip: { y: { formatter: (n) => `${n} equipamentos` } },
  states: { active: { filter: { type: "none" } } },
}));
</script>

<template>
  <DashboardChartFrame
    title="Distribuição por etapa"
    subtitle="Fluxo de aquisição de 0 a 8. Clique em uma barra para filtrar a fase."
    :empty="!ordered.length"
  >
    <ChartCanvas type="bar" :options="options" :series="series" label="Equipamentos por etapa do processo" :height="350" />
    <div v-if="props.selectedStage !== null && props.selectedStage !== undefined" class="stage-note">
      Fase {{ props.selectedStage }} filtrada — clique novamente na barra para limpar.
    </div>
  </DashboardChartFrame>
</template>

<style scoped>
.stage-note { padding: 0 10px; text-align: center; color: #697e9a; font-size: 11px; }
</style>
