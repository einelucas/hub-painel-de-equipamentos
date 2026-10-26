<script setup lang="ts">
import { computed, defineAsyncComponent } from "vue";
import type { ApexOptions } from "apexcharts";

/*
 * O ApexCharts acessa o DOM durante a inicialização. O import dinâmico +
 * ClientOnly mantém a biblioteca fora da renderização SSR e em um chunk
 * separado do restante da aplicação.
 */
const VueApexCharts = defineAsyncComponent(() => import("vue3-apexcharts"));

const props = withDefaults(
  defineProps<{
    type: "bar" | "donut" | "line";
    options: ApexOptions;
    series: NonNullable<ApexOptions["series"]>;
    label: string;
    height?: number;
  }>(),
  {
    height: 300,
  },
);

const chartOptions = computed<ApexOptions>(() => {
  const options = props.options;

  return {
    ...options,
    chart: {
      ...options.chart,
      type: props.type,
      fontFamily: "'Manrope', system-ui, sans-serif",
      foreColor: "#667085",
      background: "transparent",
      parentHeightOffset: 0,
      zoom: { enabled: false, ...options.chart?.zoom },
      toolbar: { show: false, ...options.chart?.toolbar },
    },
    tooltip: {
      theme: "light",
      ...options.tooltip,
    },
  };
});
</script>

<template>
  <ClientOnly>
    <div
      class="chart-canvas"
      role="img"
      :aria-label="props.label"
      :style="{ minHeight: `${props.height}px` }"
    >
      <VueApexCharts
        :type="props.type"
        :options="chartOptions"
        :series="props.series"
        :height="props.height"
        width="100%"
      />
    </div>

    <template #fallback>
      <div
        class="chart-canvas chart-canvas--loading"
        :style="{ height: `${props.height}px` }"
        aria-hidden="true"
      />
    </template>
  </ClientOnly>
</template>

<style scoped>
.chart-canvas {
  width: 100%;
  min-width: 0;
}

.chart-canvas--loading {
  border-radius: 10px;

  background: linear-gradient(90deg, #f3f5f8 25%, #e9edf3 50%, #f3f5f8 75%);
  background-size: 200% 100%;

  animation: chart-canvas-loading 1.4s ease infinite;
}

@keyframes chart-canvas-loading {
  from {
    background-position: 200% 0;
  }

  to {
    background-position: -200% 0;
  }
}

.chart-canvas :deep(.apexcharts-tooltip.apexcharts-theme-light) {
  border: 1px solid #e1e6ed;
  border-radius: 10px;

  background: rgb(255 255 255 / 97%);

  box-shadow: 0 8px 24px rgb(30 50 80 / 12%);

  color: #31435c;

  font-family: "Manrope", system-ui, sans-serif;
  font-size: 11.5px;
}

.chart-canvas :deep(.apexcharts-tooltip.apexcharts-theme-light .apexcharts-tooltip-title) {
  margin-bottom: 4px;
  padding: 7px 10px;

  border-bottom-color: #edf0f4;

  background: #f7f9fb;

  color: #263d5b;

  font-size: 12px;
  font-weight: 750;
}

.chart-canvas :deep(.apexcharts-tooltip-text) {
  font-family: "Manrope", system-ui, sans-serif;
}

@media (prefers-reduced-motion: reduce) {
  .chart-canvas--loading {
    animation: none;
  }
}
</style>
