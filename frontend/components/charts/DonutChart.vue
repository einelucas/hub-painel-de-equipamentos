<script setup lang="ts">
import { computed } from "vue";
import type { ApexOptions } from "apexcharts";
import { formatNumber } from "~/utils/format";

interface DonutItem {
  label: string;
  value: number;
  color: string;
}

const props = withDefaults(
  defineProps<{
    items: DonutItem[];
    suffix?: string;
    showValues?: boolean;
    showLegendValues?: boolean;
  }>(),
  {
    suffix: "%",
    showValues: true,
    showLegendValues: false,
  },
);

const safeItems = computed(() =>
  props.items.map((item) => ({
    ...item,
    value:
      Number.isFinite(item.value) && item.value > 0 ? item.value : 0,
  })),
);

const total = computed(() =>
  safeItems.value.reduce((sum, item) => sum + item.value, 0),
);

const hasData = computed(() => total.value > 0);

function formatValue(value: number): string {
  return formatNumber(value, props.suffix === "%" ? 1 : 2);
}

function valueLabel(value: number): string {
  return `${formatValue(value)}${props.suffix}`;
}

const chartSeries = computed(() => safeItems.value.map((item) => item.value));

const ariaLabel = computed(() => {
  if (!props.items.length) return "Gráfico de rosca sem dados";

  return props.items
    .map((item) => `${item.label}: ${valueLabel(item.value)}`)
    .join(", ");
});

const chartOptions = computed<ApexOptions>(() => ({
  chart: {
    type: "donut",
    animations: {
      enabled: true,
      speed: 420,
      animateGradually: { enabled: false },
      dynamicAnimation: { enabled: true, speed: 300 },
    },
  },
  labels: safeItems.value.map((item) => item.label),
  colors: safeItems.value.map((item) => item.color),
  stroke: {
    width: 3,
    colors: ["#ffffff"],
  },
  dataLabels: {
    enabled: props.showValues,
    formatter: (_value, context) => {
      const item = safeItems.value[context?.seriesIndex ?? 0];
      return item ? valueLabel(item.value) : "";
    },
    style: {
      fontFamily: "'Manrope', system-ui, sans-serif",
      fontSize: "10px",
      fontWeight: 700,
      colors: ["#ffffff"],
    },
    background: { enabled: false },
    dropShadow: {
      enabled: true,
      opacity: 0.28,
      blur: 2,
      color: "#12233a",
    },
  },
  plotOptions: {
    pie: {
      expandOnClick: false,
      dataLabels: {
        offset: 0,
        minAngleToShowLabel: 10,
      },
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
            formatter: () => valueLabel(total.value),
          },
        },
      },
    },
  },
  legend: { show: false },
  tooltip: {
    enabled: true,
    y: { formatter: (value) => valueLabel(Number(value)) },
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
  <div class="donut-chart">
    <ChartCanvas
      v-if="hasData"
      type="donut"
      :options="chartOptions"
      :series="chartSeries"
      :label="ariaLabel"
      :height="250"
    />

    <div v-else class="donut-empty" role="status">
      <span class="donut-empty-ring">Sem dados</span>
    </div>

    <ul v-if="items.length" class="donut-legend" aria-label="Legenda do gráfico">
      <li v-for="item in items" :key="item.label" class="donut-legend-item">
        <span
          class="donut-legend-dot"
          :style="{ backgroundColor: item.color }"
          aria-hidden="true"
        />

        <span>{{ item.label }}</span>

        <strong v-if="showLegendValues">
          {{ valueLabel(item.value) }}
        </strong>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.donut-chart {
  display: flex;
  width: 100%;
  min-height: 330px;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
}

.donut-empty {
  display: grid;
  min-height: 250px;
  place-items: center;
}

.donut-empty-ring {
  display: grid;
  width: 170px;
  height: 170px;
  place-items: center;

  border: 16px solid #f0f2f5;
  border-radius: 999px;

  color: #98a2b3;

  font-size: 12px;
  font-weight: 600;
}

.donut-legend {
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;
  gap: 8px 14px;

  margin: 0;
  padding: 0;

  list-style: none;
}

.donut-legend-item {
  display: inline-flex;
  align-items: center;
  gap: 5px;

  color: #667085;

  font-size: 12px;
  white-space: nowrap;
}

.donut-legend-item strong {
  margin-left: 2px;

  color: #344054;

  font-weight: 700;
}

.donut-legend-dot {
  width: 9px;
  height: 9px;
  flex: 0 0 9px;

  border-radius: 999px;
}

@media (max-width: 768px) {
  .donut-chart {
    min-height: 285px;
  }

  .donut-empty,
  .donut-empty-ring {
    min-height: auto;
  }

  .donut-empty-ring {
    width: 150px;
    height: 150px;
  }

  .donut-legend-item {
    font-size: 11px;
  }
}
</style>
