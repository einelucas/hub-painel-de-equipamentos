<script setup lang="ts">
import { computed } from "vue";
import type { ApexOptions } from "apexcharts";
import type { AnalyticsDistributionItem } from "~/types/dashboardAnalytics";
import { CHART_COLORS, FONT_FAMILY, visibleTop } from "~/utils/dashboardAnalytics";

const props = withDefaults(defineProps<{
  title: string;
  subtitle: string;
  items: AnalyticsDistributionItem[];
  loading?: boolean;
  limit?: number;
}>(), { loading: false, limit: 10 });
const display = computed(() => visibleTop(props.items, props.limit));
const series = computed(() => [{ name: "Equipamentos", data: display.value.visible.map((item) => item.count) }]);
const labels = computed(() => display.value.visible.map((item) => item.label));
const options = computed<ApexOptions>(() => ({
  chart: { type: "bar" },
  colors: [CHART_COLORS.primary],
  plotOptions: { bar: { horizontal: true, barHeight: "57%", borderRadius: 4 } },
  xaxis: { categories: labels.value, labels: { formatter: (v) => String(Math.round(Number(v))) } },
  yaxis: { labels: { maxWidth: 180, style: { fontSize: "10px", fontFamily: FONT_FAMILY } } },
  dataLabels: {
    enabled: true,
    formatter: (v) => String(Math.round(Number(v))),
    style: {
      colors: ["#ffffff"],
      fontWeight: 700,
      fontSize: "11px",
      fontFamily: FONT_FAMILY,
    },
    background: { enabled: false },
    dropShadow: { enabled: false },
  },
  grid: { borderColor: CHART_COLORS.border, padding: { right: 12 } },
  legend: { show: false },
  tooltip: { y: { formatter: (n) => `${n} equipamentos` } },
}));
const height = computed(() => Math.max(260, display.value.visible.length * 38 + 60));
</script>

<template>
  <DashboardChartFrame
    :title="props.title"
    :subtitle="props.subtitle"
    :loading="props.loading"
    :empty="!display.visible.length"
    :note="display.omitted ? `Exibindo os ${display.visible.length} maiores grupos; ${display.omitted} outros não aparecem nesta visualização.` : ''"
  >
    <ChartCanvas type="bar" :options="options" :series="series" :label="props.title" :height="height" />
  </DashboardChartFrame>
</template>
