<script setup lang="ts">
import { computed, defineAsyncComponent, ref } from "vue";
import type { ApexOptions } from "apexcharts";

/** O ApexCharts acessa o DOM: import dinâmico + ClientOnly (SSR seguro). */
const VueApexCharts = defineAsyncComponent(() => import("vue3-apexcharts"));

interface Item {
  label: string;
  value: number;
  color: string;
}

const props = defineProps<{ items: Item[]; suffix?: string }>();

const suffix = computed(() => props.suffix ?? "%");

const safeItems = computed(() =>
  props.items.map((item) => ({
    ...item,
    value: Number.isFinite(item.value) && item.value > 0 ? item.value : 0,
  })),
);

const total = computed(() =>
  safeItems.value.reduce((sum, item) => sum + item.value, 0),
);

const hasData = computed(() => total.value > 0);

const chartSeries = computed(() => safeItems.value.map((item) => item.value));
const chartLabels = computed(() => safeItems.value.map((item) => item.label));
const chartColors = computed(() => safeItems.value.map((item) => item.color));

function formatValue(value: number): string {
  return new Intl.NumberFormat("pt-BR", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

const apexRef = ref<InstanceType<typeof VueApexCharts> | null>(null);

/** Fatias ocultas pelo clique na legenda (ficam acinzentadas, como no gráfico de situação de prazos). */
const hiddenLabels = ref<Set<string>>(new Set());

function toggleSlice(index: number, seriesName: string): void {
  const next = new Set(hiddenLabels.value);
  if (next.has(seriesName)) next.delete(seriesName);
  else next.add(seriesName);
  hiddenLabels.value = next;
  apexRef.value?.chart?.toggleSeries(seriesName);
}

const chartOptions = computed<ApexOptions>(() => ({
  chart: {
    type: "donut",
    width: "100%",
    height: 300,
    toolbar: { show: false },
    animations: { enabled: true, speed: 420 },
  },
  series: chartSeries.value,
  labels: chartLabels.value,
  colors: chartColors.value,
  stroke: { width: 3, colors: ["#ffffff"] },
  dataLabels: {
    enabled: true,
    formatter: (_value, context) => {
      const item = safeItems.value[context?.seriesIndex ?? 0];
      return item ? `${formatValue(item.value)}${suffix.value}` : "";
    },
    style: {
      fontFamily: "'Manrope', system-ui, sans-serif",
      fontSize: "10px",
      fontWeight: 700,
      colors: ["#ffffff"],
    },
    background: { enabled: false },
    dropShadow: { enabled: true, opacity: 0.28, blur: 2, color: "#12233a" },
  },
  plotOptions: {
    pie: {
      expandOnClick: true,
      dataLabels: { offset: 0, minAngleToShowLabel: 10 },
      donut: {
        size: "68%",
        labels: {
          show: true,
          name: { show: false },
          value: { show: false },
          total: {
            show: true,
            showAlways: true,
            label: "Total",
            color: "#7f8998",
            fontFamily: "'Manrope', system-ui, sans-serif",
            fontSize: "11px",
            fontWeight: 600,
            formatter: () => `${formatValue(total.value)}${suffix.value}`,
          },
        },
      },
    },
  },
  legend: { show: false },
  tooltip: {
    y: { formatter: (value) => `${formatValue(Number(value))}${suffix.value}` },
  },
  noData: { text: "Sem dados", align: "center", verticalAlign: "middle" },
}));

const ariaLabel = computed(() =>
  props.items.map((item) => `${item.label}: ${formatValue(item.value)}${suffix.value}`).join(", "),
);
</script>

<template>
  <ClientOnly>
    <div v-if="hasData" class="situation-donut" role="img" :aria-label="ariaLabel">
      <div class="donut-wrap">
        <VueApexCharts ref="apexRef" type="donut" :options="chartOptions" :series="chartSeries" width="100%" />
      </div>
      <ul class="donut-legend">
        <li
          v-for="(item, index) in safeItems"
          :key="item.label"
          class="donut-legend-item"
          :class="{ 'donut-legend-item--hidden': hiddenLabels.has(item.label) }"
          :style="{ '--color': item.color, opacity: hiddenLabels.has(item.label) ? 0.45 : 1 }"          role="button"
          tabindex="0"
          :aria-pressed="!hiddenLabels.has(item.label)"
          @click="toggleSlice(index, item.label)"
          @keydown.enter.prevent="toggleSlice(index, item.label)"
          @keydown.space.prevent="toggleSlice(index, item.label)"
        >
          <span class="donut-legend-dot" :style="{ background: item.color }" aria-hidden="true" />
          <span>{{ item.label }} {{ formatValue(item.value) }}{{ suffix }}</span>
        </li>
      </ul>
    </div>
    <div v-else class="situation-donut situation-donut--empty" role="status">
      <span>Sem dados</span>
    </div>
  </ClientOnly>
</template>

<style scoped>
.situation-donut { width: 100%; min-height: 320px; display: flex; align-items: center; justify-content: center; flex-direction: column; }
.situation-donut--empty { color: #98a2b3; font-size: 12px; font-weight: 600; }
.donut-wrap { width: 100%; max-width: 280px; }
.donut-legend { display: flex; justify-content: center; gap: 14px; list-style: none; margin: 10px 0 0; padding: 0; flex-wrap: wrap; }
.donut-legend-item { display: flex; align-items: center; gap: 6px; font-size: 13px; font-weight: 700; color: #475569; white-space: nowrap; line-height: 1; cursor: pointer; transition: opacity 0.15s ease; }
.donut-legend-item--hidden { opacity: 0.45; }
.donut-legend-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
</style>
