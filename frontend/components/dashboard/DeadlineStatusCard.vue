<script setup lang="ts">
import { Clock } from "lucide-vue-next";
import type { DeadlinesSummary, WorkNeedStatus } from "~/types/equipment";
import { formatNumber } from "~/utils/format";
import { workNeedStatusLabel } from "~/utils/workNeedStatus";

const props = defineProps<{
  deadlines: DeadlinesSummary;
}>();

interface DeadlineRow {
  key: WorkNeedStatus;
  label: string;
  count: number;
  type: "critical" | "warning" | "safe";
}

const rows = computed<DeadlineRow[]>(() => [
  {
    key: "CHECK_DELIVERY_FUP",
    label: workNeedStatusLabel("CHECK_DELIVERY_FUP"),
    count: props.deadlines.checkDeliveryFup,
    type: "critical",
  },
  {
    key: "NEEDED_TODAY",
    label: workNeedStatusLabel("NEEDED_TODAY"),
    count: props.deadlines.neededToday,
    type: "critical",
  },
  {
    key: "LT_30_DAYS",
    label: workNeedStatusLabel("LT_30_DAYS"),
    count: props.deadlines.lt30Days,
    type: "critical",
  },
  {
    key: "LT_60_DAYS",
    label: workNeedStatusLabel("LT_60_DAYS"),
    count: props.deadlines.lt60Days,
    type: "warning",
  },
  {
    key: "LT_90_DAYS",
    label: workNeedStatusLabel("LT_90_DAYS"),
    count: props.deadlines.lt90Days,
    type: "warning",
  },
  {
    key: "SAFE",
    label: workNeedStatusLabel("SAFE"),
    count: props.deadlines.safe,
    type: "safe",
  },
]);

const calculatedTotal = computed(() =>
  rows.value.reduce((total, row) => total + row.count, 0),
);

const safePercentage = computed(() => {
  if (calculatedTotal.value === 0) return 0;

  return (props.deadlines.safe / calculatedTotal.value) * 100;
});

const riskTotal = computed(
  () =>
    props.deadlines.checkDeliveryFup +
    props.deadlines.neededToday +
    props.deadlines.lt30Days,
);

const warningTotal = computed(
  () => props.deadlines.lt60Days + props.deadlines.lt90Days,
);

function percentage(value: number): number {
  if (!calculatedTotal.value) return 0;

  return (value / calculatedTotal.value) * 100;
}
</script>

<template>
  <DashboardCard
    title="Situação de prazos"
    subtitle="Status necessidade da obra (limite de entrega em obra)."
    :icon="Clock"
  >
    <p
      v-if="!deadlines.available"
      class="not-calculated"
      data-testid="deadlines-unavailable"
    >
      Indicador aguardando definição da regra de prazo.

      <small>
        {{ deadlines.reason }}
      </small>
    </p>

    <div v-else class="deadlines" data-testid="deadlines-summary">
      <!-- Resumo principal -->
      <div class="summary">
        <div class="summary-total">
          <strong>
            {{ formatNumber(calculatedTotal, 0) }}
          </strong>

          <span>com prazo calculável</span>
        </div>

        <div class="summary-safe">
          <strong> {{ safePercentage.toFixed(1).replace(".", ",") }}% </strong>

          <span>prazo seguro</span>
        </div>
      </div>

      <!-- Barra de distribuição -->
      <div class="distribution">
        <div class="distribution-track">
          <span
            v-if="riskTotal"
            class="distribution-part distribution-part--critical"
            :style="{
              width: `${percentage(riskTotal)}%`,
            }"
          />

          <span
            v-if="warningTotal"
            class="distribution-part distribution-part--warning"
            :style="{
              width: `${percentage(warningTotal)}%`,
            }"
          />

          <span
            v-if="deadlines.safe"
            class="distribution-part distribution-part--safe"
            :style="{
              width: `${percentage(deadlines.safe)}%`,
            }"
          />
        </div>

        <div class="distribution-caption">
          <span>
            <i class="dot dot--critical" />
            Crítico
            <strong>{{ formatNumber(riskTotal, 0) }}</strong>
          </span>

          <span>
            <i class="dot dot--warning" />
            Atenção
            <strong>{{ formatNumber(warningTotal, 0) }}</strong>
          </span>

          <span>
            <i class="dot dot--safe" />
            Seguro
            <strong>{{ formatNumber(deadlines.safe, 0) }}</strong>
          </span>
        </div>
      </div>

      <!-- Detalhamento -->
      <div class="status-grid">
        <div v-for="row in rows" :key="row.key" class="status-item">
          <span
            class="status-indicator"
            :class="`status-indicator--${row.type}`"
          />

          <span class="status-label">
            {{ row.label }}
          </span>

          <strong class="status-value">
            {{ formatNumber(row.count, 0) }}
          </strong>
        </div>
      </div>

      <!-- Sem prazo -->
      <div class="without-deadline">
        <span>Sem prazo calculável</span>

        <strong>
          {{ formatNumber(deadlines.withoutDeadline, 0) }}
        </strong>
      </div>
    </div>
  </DashboardCard>
</template>

<style scoped>
.not-calculated {
  display: grid;
  gap: 7px;

  margin: 0;

  color: #9b6418;

  font-size: 12.5px;
  font-weight: 700;
}

.not-calculated small {
  color: #8b96a5;

  font-size: 11px;
  font-weight: 500;
}

/* Container */

.deadlines {
  display: flex;
  height: 100%;
  flex-direction: column;
  gap: 16px;
}

/* =========================================================
   RESUMO
   ========================================================= */

.summary {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 18px;
}

.summary-total,
.summary-safe {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.summary-total strong {
  color: #18345c;

  font-size: 28px;
  font-weight: 750;
  line-height: 1;
}

.summary-total span {
  color: #8b96a5;

  font-size: 11px;
  font-weight: 500;
}

.summary-safe {
  align-items: flex-end;
  text-align: right;
}

.summary-safe strong {
  color: #487c39;

  font-size: 21px;
  font-weight: 750;
  line-height: 1;
}

.summary-safe span {
  color: #7d8a78;

  font-size: 9px;
  font-weight: 700;

  letter-spacing: 0.045em;
  text-transform: uppercase;
}

/* =========================================================
   DISTRIBUIÇÃO
   ========================================================= */

.distribution {
  display: grid;
  gap: 8px;
}

.distribution-track {
  display: flex;
  width: 100%;
  height: 9px;

  overflow: hidden;

  border-radius: 999px;

  background: #edf1f5;
}

.distribution-part {
  display: block;
  height: 100%;

  transition: width 0.25s ease;
}

.distribution-part--critical {
  background: #c96a6a;
}

.distribution-part--warning {
  background: #d3a24d;
}

.distribution-part--safe {
  background: #609150;
}

.distribution-caption {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
}

.distribution-caption > span {
  display: inline-flex;
  align-items: center;
  gap: 5px;

  color: #7b8798;

  font-size: 10.5px;
}

.distribution-caption strong {
  color: #536176;
  font-weight: 700;
}

.dot {
  display: inline-block;
  width: 6px;
  height: 6px;

  border-radius: 50%;
}

.dot--critical {
  background: #c96a6a;
}

.dot--warning {
  background: #d3a24d;
}

.dot--safe {
  background: #609150;
}

/* =========================================================
   DETALHAMENTO
   ========================================================= */

.status-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 7px 20px;

  padding-top: 2px;
}

.status-item {
  display: grid;
  grid-template-columns: 7px minmax(0, 1fr) auto;
  align-items: center;
  gap: 7px;

  min-width: 0;
}

.status-indicator {
  width: 6px;
  height: 6px;

  border-radius: 50%;
}

.status-indicator--critical {
  background: #c96a6a;
}

.status-indicator--warning {
  background: #d3a24d;
}

.status-indicator--safe {
  background: #609150;
}

.status-label {
  overflow: hidden;

  color: #657286;

  font-size: 10.5px;
  font-weight: 500;

  text-overflow: ellipsis;
  white-space: nowrap;
}

.status-value {
  color: #34455e;

  font-size: 11px;
  font-weight: 750;
}

/* =========================================================
   SEM PRAZO
   ========================================================= */

.without-deadline {
  display: flex;
  align-items: center;
  justify-content: space-between;

  margin-top: auto;
  padding-top: 10px;

  border-top: 1px solid #edf0f4;

  color: #8b96a5;

  font-size: 10.5px;
  font-weight: 500;
}

.without-deadline strong {
  color: #7c899a;

  font-size: 11px;
}

/* Responsividade */

@media (max-width: 520px) {
  .status-grid {
    grid-template-columns: 1fr;
  }

  .distribution-caption {
    gap: 7px 12px;
  }
}
</style>
