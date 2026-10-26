<script setup lang="ts">
import { computed } from "vue";
import type { ApexOptions } from "apexcharts";
import { formatNumber } from "~/utils/format";

interface BarPoint {
  label: string;
  value: number | null;
}

const props = withDefaults(
  defineProps<{
    points: BarPoint[];
    target?: number | null;
    suffix?: string;
    color?: string;
    seriesLabel?: string;
    showLegend?: boolean;
    showValues?: boolean;
  }>(),
  {
    target: null,
    suffix: "",
    color: "#304f7e",
    seriesLabel: "Resultado",
    showLegend: true,
    showValues: true,
  },
);

const validValues = computed(() =>
  props.points
    .map((point) => point.value)
    .filter(
      (value): value is number =>
        typeof value === "number" && Number.isFinite(value),
    ),
);

function niceStep(value: number): number {
  if (value <= 0) return 1;

  const roughStep = value / 4;
  const magnitude = 10 ** Math.floor(Math.log10(roughStep));
  const normalized = roughStep / magnitude;

  let nice = 1;

  if (normalized <= 1) {
    nice = 1;
  } else if (normalized <= 2) {
    nice = 2;
  } else if (normalized <= 5) {
    nice = 5;
  } else {
    nice = 10;
  }

  return nice * magnitude;
}

const yMax = computed(() => {
  const rawMax = Math.max(1, ...validValues.value, props.target ?? 0);

  if (props.suffix === "%" && rawMax <= 100) {
    return 100;
  }

  const step = niceStep(rawMax);

  return Math.max(step, Math.ceil(rawMax / step) * step);
});

const chartSeries = computed(() => [
  {
    name: props.seriesLabel,
    data: props.points.map((point) =>
      typeof point.value === "number" && Number.isFinite(point.value)
        ? point.value
        : null,
    ),
  },
]);

function formatValue(value: number): string {
  return formatNumber(value, props.suffix === "%" ? 1 : 2);
}

function valueLabel(value: number): string {
  return `${formatValue(value)}${props.suffix}`;
}

const inlineValues = computed(
  () => props.showValues && props.points.length <= 10,
);

const ariaLabel = computed(() => {
  if (!props.points.length) return "Gráfico de barras sem dados";

  return props.points
    .map((point) =>
      point.value === null
        ? `${point.label}: sem dados`
        : `${point.label}: ${valueLabel(point.value)}`,
    )
    .join(", ");
});

const chartOptions = computed<ApexOptions>(() => ({
  chart: {
    type: "bar",
    animations: {
      enabled: true,
      speed: 420,
      animateGradually: { enabled: false },
      dynamicAnimation: { enabled: true, speed: 300 },
    },
  },
  colors: [props.color],
  plotOptions: {
    bar: {
      columnWidth: "54%",
      borderRadius: 7,
      borderRadiusApplication: "end",
    },
  },
  dataLabels: {
    enabled: inlineValues.value,
    offsetY: -18,
    formatter: (value) => {
      const numericValue = Number(value);
      return Number.isFinite(numericValue) ? valueLabel(numericValue) : "";
    },
    style: {
      fontFamily: "'Manrope', system-ui, sans-serif",
      fontSize: "10px",
      fontWeight: 700,
      colors: ["#2d425f"],
    },
    background: { enabled: false },
    dropShadow: { enabled: false },
  },
  stroke: { show: false, width: 0 },
  grid: {
    borderColor: "#e9eef4",
    strokeDashArray: 0,
    xaxis: { lines: { show: false } },
    yaxis: { lines: { show: true } },
    padding: { top: 8, right: 10, bottom: 0, left: 4 },
  },
  xaxis: {
    categories: props.points.map((point) => point.label),
    axisBorder: { show: true, color: "#a7b1bf", strokeWidth: 1 },
    axisTicks: { show: false },
    crosshairs: { show: false },
    labels: {
      rotate: -30,
      rotateAlways: false,
      hideOverlappingLabels: true,
      trim: true,
      maxHeight: 84,
      style: {
        fontFamily: "'Manrope', system-ui, sans-serif",
        fontSize: "10px",
        fontWeight: 500,
        colors: "#7f8998",
      },
    },
  },
  yaxis: {
    min: 0,
    max: yMax.value,
    tickAmount: 4,
    labels: {
      formatter: (value) => valueLabel(value),
      style: {
        fontFamily: "'Manrope', system-ui, sans-serif",
        fontSize: "9.5px",
        fontWeight: 500,
        colors: "#7f8998",
      },
    },
    axisBorder: { show: false },
    axisTicks: { show: false },
  },
  annotations:
    props.target === null
      ? undefined
      : {
          yaxis: [
            {
              y: props.target,
              borderColor: "#e0a348",
              strokeDashArray: 5,
              label: {
                text: `Meta ${valueLabel(props.target)}`,
                borderColor: "transparent",
                position: "right",
                offsetX: -4,
                style: {
                  background: "#ffffff",
                  color: "#9a6a25",
                  fontFamily: "'Manrope', system-ui, sans-serif",
                  fontSize: "10px",
                  fontWeight: 650,
                  padding: { left: 4, right: 4, top: 2, bottom: 2 },
                },
              },
            },
          ],
        },
  legend: { show: false },
  tooltip: {
    enabled: true,
    x: { show: true },
    y: { formatter: (value) => valueLabel(Number(value)) },
    marker: { show: true },
  },
  noData: {
    text: "Sem dados",
    align: "center",
    verticalAlign: "middle",
    style: {
      color: "#98a2b3",
      fontFamily: "'Manrope', system-ui, sans-serif",
      fontSize: "12px",
      fontWeight: 600,
    },
  },
}));
</script>

<template>
  <div class="bar-chart">
    <ChartCanvas
      type="bar"
      :options="chartOptions"
      :series="chartSeries"
      :label="ariaLabel"
      :height="300"
    />

    <div v-if="props.showLegend" class="chart-legend">
      <span class="chart-legend-item">
        <span class="chart-legend-square" :style="{ backgroundColor: color }" />
        <span>{{ props.seriesLabel }}{{ props.suffix ? ` (${props.suffix})` : "" }}</span>
      </span>

      <span v-if="props.target !== null" class="chart-legend-item">
        <span class="chart-legend-target" />
        <span>Meta {{ valueLabel(props.target) }}</span>
      </span>
    </div>
  </div>
</template>

<style scoped>
.bar-chart {
  display: flex;
  width: 100%;
  min-height: 310px;
  flex-direction: column;
  align-items: stretch;
  justify-content: center;
}

.chart-legend {
  display: flex;
  min-height: 28px;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;
  gap: 8px 18px;

  color: #69778c;

  font-size: 11px;
}

.chart-legend-item {
  display: inline-flex;
  align-items: center;
  gap: 7px;
}

.chart-legend-square {
  width: 8px;
  height: 8px;

  border-radius: 3px;
}

.chart-legend-target {
  width: 20px;
  height: 0;

  border-top: 2px dashed #e0a348;
}

@media (max-width: 768px) {
  .bar-chart {
    min-height: 285px;
  }

  .chart-legend {
    font-size: 10.5px;
  }
}
</style>
