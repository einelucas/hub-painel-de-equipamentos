<script setup lang="ts">
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

const hoveredIndex = ref<number | null>(null);

const width = 760;
const height = 300;

const pad = {
  left: 52,
  right: 22,
  top: 30,
  bottom: 76,
};

const plotWidth = width - pad.left - pad.right;
const plotHeight = height - pad.top - pad.bottom;

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

const max = computed(() => {
  const rawMax = Math.max(1, ...validValues.value, props.target ?? 0);

  if (props.suffix === "%" && rawMax <= 100) {
    return 100;
  }

  const step = niceStep(rawMax);

  return Math.max(step, Math.ceil(rawMax / step) * step);
});

const slot = computed(() => plotWidth / Math.max(1, props.points.length));

const barWidth = computed(() => Math.min(54, Math.max(22, slot.value * 0.5)));

const x = (index: number) => pad.left + index * slot.value + slot.value / 2;

const barX = (index: number) => x(index) - barWidth.value / 2;

const y = (value: number) =>
  height - pad.bottom - (value / max.value) * plotHeight;

const barHeight = (value: number) =>
  Math.max(0, height - pad.bottom - y(value));

const yTicks = computed(() => {
  if (props.suffix === "%" && max.value === 100) {
    return [100, 75, 50, 25, 0].map((value) => ({
      value,
      y: y(value),
    }));
  }

  const step = niceStep(max.value);
  const ticks: { value: number; y: number }[] = [];

  for (let value = max.value; value >= 0; value -= step) {
    ticks.push({
      value,
      y: y(value),
    });
  }

  return ticks;
});

const targetY = computed(() => {
  if (props.target === null) {
    return null;
  }

  return y(props.target);
});

interface HoveredBarPoint {
  label: string;
  value: number;
  index: number;
}

const hoveredPoint = computed<HoveredBarPoint | null>(() => {
  const index = hoveredIndex.value;

  if (index === null) {
    return null;
  }

  const point = props.points[index];
  const value = point?.value;

  if (!point || typeof value !== "number" || !Number.isFinite(value)) {
    return null;
  }

  return {
    label: point.label,
    value,
    index,
  };
});

const tooltipStyle = computed(() => {
  if (!hoveredPoint.value) {
    return {};
  }

  const px = (x(hoveredPoint.value.index) / width) * 100;
  const py = (y(hoveredPoint.value.value) / height) * 100;
  const alignRight = px > 62;

  return {
    left: `${px}%`,
    top: `${py}%`,
    transform: `translate(${alignRight ? "-100%" : "0%"}, -100%) translate(${alignRight ? "-10px" : "10px"}, -10px)`,
  };
});

const showInlineValues = computed(
  () => props.showValues && props.points.length <= 10,
);

const legendText = computed(() =>
  props.suffix ? `${props.seriesLabel} (${props.suffix})` : props.seriesLabel,
);

const ariaLabel = computed(() =>
  props.points
    .map((point) =>
      point.value === null
        ? `${point.label}: sem dados`
        : `${point.label}: ${formatValue(point.value)}${props.suffix}`,
    )
    .join(", "),
);

function formatValue(value: number) {
  return new Intl.NumberFormat("pt-BR", {
    maximumFractionDigits: 2,
  }).format(value);
}

function labelLines(label: string): string[] {
  const clean = label.trim();
  const maxLength = 14;

  if (clean.length <= maxLength) {
    return [clean];
  }

  const words = clean.split(/\s+/);
  const lines: string[] = [];
  let current = "";

  for (const word of words) {
    const candidate = current ? `${current} ${word}` : word;

    if (candidate.length <= maxLength) {
      current = candidate;
      continue;
    }

    if (current) {
      lines.push(current);
    }

    current = word;

    if (lines.length === 1) {
      break;
    }
  }

  if (current && lines.length < 2) {
    lines.push(current);
  }

  if (lines.length === 1 && lines[0]!.length > maxLength + 5) {
    lines[0] = `${lines[0]!.slice(0, maxLength + 2)}…`;
  }

  return lines.slice(0, 2);
}

function valueLabelY(value: number): number {
  if (value === 0) {
    return height - pad.bottom - 10;
  }

  return Math.max(pad.top + 13, y(value) - 8);
}

function roundedTopBarPath(index: number, value: number): string {
  const bx = barX(index);
  const by = y(value);
  const bw = barWidth.value;
  const bh = barHeight(value);

  if (bh <= 0) {
    return "";
  }

  const radius = Math.min(8, bw / 2, bh);
  const bottom = height - pad.bottom;

  return [
    `M ${bx} ${bottom}`,
    `L ${bx} ${by + radius}`,
    `Q ${bx} ${by} ${bx + radius} ${by}`,
    `L ${bx + bw - radius} ${by}`,
    `Q ${bx + bw} ${by} ${bx + bw} ${by + radius}`,
    `L ${bx + bw} ${bottom}`,
    "Z",
  ].join(" ");
}

function activate(index: number) {
  hoveredIndex.value = index;
}

function deactivate(index: number) {
  if (hoveredIndex.value === index) {
    hoveredIndex.value = null;
  }
}
</script>

<template>
  <div class="bar-chart">
    <div class="chart-stage">
      <svg
        class="chart-svg"
        :viewBox="`0 0 ${width} ${height}`"
        role="img"
        :aria-label="ariaLabel"
        preserveAspectRatio="xMidYMid meet"
      >
        <!-- Grade horizontal -->
        <g v-for="tick in yTicks" :key="tick.value">
          <line
            :x1="pad.left"
            :x2="width - pad.right"
            :y1="tick.y"
            :y2="tick.y"
            class="chart-grid-line"
          />

          <text
            :x="pad.left - 10"
            :y="tick.y + 4"
            text-anchor="end"
            class="chart-axis-label"
          >
            {{ formatValue(tick.value) }}{{ suffix }}
          </text>
        </g>

        <!-- Eixos -->
        <line
          :x1="pad.left"
          :x2="pad.left"
          :y1="pad.top"
          :y2="height - pad.bottom"
          class="chart-axis chart-axis--vertical"
        />

        <line
          :x1="pad.left"
          :x2="width - pad.right"
          :y1="height - pad.bottom"
          :y2="height - pad.bottom"
          class="chart-axis"
        />

        <!-- Meta -->
        <template v-if="target !== null && targetY !== null">
          <line
            :x1="pad.left"
            :x2="width - pad.right"
            :y1="targetY"
            :y2="targetY"
            class="chart-target"
          />

          <text
            :x="width - pad.right - 2"
            :y="targetY - 8"
            text-anchor="end"
            class="chart-target-label"
          >
            Meta {{ formatValue(target) }}{{ suffix }}
          </text>
        </template>

        <!-- Destaque extremamente sutil da categoria em hover -->
        <rect
          v-if="hoveredPoint"
          :x="pad.left + hoveredPoint.index * slot"
          :y="pad.top"
          :width="slot"
          :height="plotHeight"
          rx="8"
          class="chart-hover-band"
        />

        <template
          v-for="(point, index) in points"
          :key="`${point.label}-${index}`"
        >
          <template v-if="point.value !== null && Number.isFinite(point.value)">
            <!--
              Valores zero não recebem uma falsa "barra vazia".
              Um pequeno marcador na linha de base comunica o zero.
            -->
            <circle
              v-if="point.value === 0"
              :cx="x(index)"
              :cy="height - pad.bottom"
              r="3.5"
              class="chart-zero"
              :class="{ 'chart-zero--active': hoveredIndex === index }"
            />

            <!-- Barra somente quando existe valor positivo -->
            <path
              v-else
              :d="roundedTopBarPath(index, point.value)"
              :fill="color"
              class="chart-bar"
              :class="{
                'chart-bar--active': hoveredIndex === index,
                'chart-bar--muted':
                  hoveredIndex !== null && hoveredIndex !== index,
              }"
              role="graphics-symbol"
              :aria-label="`${point.label}: ${formatValue(point.value)}${suffix}`"
              tabindex="0"
              @mouseenter="activate(index)"
              @mouseleave="deactivate(index)"
              @focus="activate(index)"
              @blur="deactivate(index)"
            >
              <title>
                {{ point.label }}: {{ formatValue(point.value) }}{{ suffix }}
              </title>
            </path>

            <!-- Valor -->
            <text
              v-if="showInlineValues || hoveredIndex === index"
              :x="x(index)"
              :y="valueLabelY(point.value)"
              text-anchor="middle"
              class="chart-value-label"
              :class="{ 'chart-value-label--active': hoveredIndex === index }"
            >
              {{ formatValue(point.value) }}{{ suffix }}
            </text>

            <!-- Área de interação ampliada -->
            <rect
              :x="pad.left + index * slot"
              :y="pad.top"
              :width="slot"
              :height="plotHeight + 48"
              fill="transparent"
              class="chart-hit-area"
              tabindex="0"
              :aria-label="`${point.label}: ${formatValue(point.value)}${suffix}`"
              @mouseenter="activate(index)"
              @mouseleave="deactivate(index)"
              @focus="activate(index)"
              @blur="deactivate(index)"
            />
          </template>

          <!-- Rótulo X em até duas linhas -->
          <text
            :x="x(index)"
            :y="height - 40"
            text-anchor="middle"
            class="chart-x-label"
            :class="{ 'chart-x-label--active': hoveredIndex === index }"
          >
            <tspan
              v-for="(line, lineIndex) in labelLines(point.label)"
              :key="`${line}-${lineIndex}`"
              :x="x(index)"
              :dy="lineIndex === 0 ? 0 : 12"
            >
              {{ line }}
            </tspan>
          </text>
        </template>
      </svg>

      <!-- Tooltip -->
      <div v-if="hoveredPoint" class="chart-tooltip" :style="tooltipStyle">
        <div class="chart-tooltip-title">
          {{ hoveredPoint.label }}
        </div>

        <div class="chart-tooltip-row">
          <span class="chart-tooltip-dot" :style="{ backgroundColor: color }" />

          <span>
            {{ seriesLabel }}:
            <strong> {{ formatValue(hoveredPoint.value) }}{{ suffix }} </strong>
          </span>
        </div>

        <div v-if="target !== null" class="chart-tooltip-row">
          <span class="chart-tooltip-dot chart-tooltip-dot--target" />

          <span>
            Meta:
            <strong>{{ formatValue(target) }}{{ suffix }}</strong>
          </span>
        </div>
      </div>
    </div>

    <!-- Legenda -->
    <div v-if="showLegend" class="chart-legend">
      <span class="chart-legend-item">
        <span class="chart-legend-square" :style="{ backgroundColor: color }" />
        <span>{{ legendText }}</span>
      </span>

      <span v-if="target !== null" class="chart-legend-item">
        <span class="chart-legend-target" />
        <span>Meta {{ formatValue(target) }}{{ suffix }}</span>
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

.chart-stage {
  position: relative;
  width: 100%;
}

.chart-svg {
  display: block;
  width: 100%;
  height: auto;
  overflow: visible;
}

/* Grade */

.chart-grid-line {
  stroke: #e9eef4;
  stroke-width: 1;
}

.chart-axis {
  stroke: #a7b1bf;
  stroke-width: 1;
}

.chart-axis--vertical {
  opacity: 0.7;
}

.chart-axis-label,
.chart-x-label {
  fill: #7f8998;
  font-size: 9.5px;
  font-weight: 500;

  transition:
    fill 0.15s ease,
    font-weight 0.15s ease;
}

.chart-x-label--active {
  fill: #243b5a;
  font-weight: 750;
}

/* Meta */

.chart-target {
  stroke: #e0a348;
  stroke-width: 1.4;
  stroke-dasharray: 7 6;
  pointer-events: none;
}

.chart-target-label {
  fill: #9a6a25;
  font-size: 9.5px;
  font-weight: 650;
  pointer-events: none;
}

/*
 * Hover discreto.
 * Não compete visualmente com as barras.
 */
.chart-hover-band {
  fill: rgb(47 79 126 / 3%);
  pointer-events: none;
}

/* Barra */

.chart-bar {
  cursor: pointer;
  opacity: 0.9;
  outline: none;

  transform-box: fill-box;
  transform-origin: center bottom;

  transition:
    opacity 0.18s ease,
    filter 0.18s ease,
    transform 0.18s ease;
}

.chart-bar--active {
  opacity: 1;

  filter: drop-shadow(0 5px 8px rgb(28 50 82 / 14%));

  transform: scaleX(1.04);
}

.chart-bar--muted {
  opacity: 0.55;
}

.chart-bar:focus-visible {
  stroke: #1f3553;
  stroke-width: 2;
}

/* Zero */

.chart-zero {
  fill: #c7d0dc;

  transition:
    fill 0.15s ease,
    r 0.15s ease;
}

.chart-zero--active {
  fill: #60758f;
  r: 4.5px;
}

/* Valor das barras */

.chart-value-label {
  fill: #2d425f;

  font-size: 9.5px;
  font-weight: 700;

  pointer-events: none;

  transition:
    fill 0.15s ease,
    font-weight 0.15s ease;
}

.chart-value-label--active {
  fill: #17375f;
  font-weight: 800;
}

.chart-hit-area {
  cursor: pointer;
  outline: none;
}

/* Tooltip */

.chart-tooltip {
  position: absolute;
  z-index: 5;

  min-width: 150px;
  padding: 10px 12px;

  border: 1px solid #e1e6ed;
  border-radius: 10px;

  background: rgb(255 255 255 / 97%);

  box-shadow: 0 8px 24px rgb(30 50 80 / 12%);

  color: #31435c;

  font-size: 11.5px;

  pointer-events: none;
}

.chart-tooltip-title {
  margin-bottom: 7px;

  color: #263d5b;

  font-size: 12px;
  font-weight: 750;
}

.chart-tooltip-row {
  display: flex;
  align-items: center;
  gap: 6px;

  padding: 2px 0;

  color: #718096;
}

.chart-tooltip-row strong {
  color: #31435c;
}

.chart-tooltip-dot {
  width: 7px;
  height: 7px;
  flex-shrink: 0;

  border-radius: 50%;
}

.chart-tooltip-dot--target {
  background: #e0a348;
}

/* Legenda */

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

/* Responsividade */

@media (max-width: 768px) {
  .bar-chart {
    min-height: 285px;
  }

  .chart-axis-label,
  .chart-x-label {
    font-size: 8.7px;
  }

  .chart-value-label {
    font-size: 8.8px;
  }

  .chart-tooltip {
    min-width: 140px;
    padding: 8px 10px;
    font-size: 11px;
  }

  .chart-legend {
    font-size: 10.5px;
  }
}
</style>
