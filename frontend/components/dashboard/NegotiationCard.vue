<script setup lang="ts">
import { computed } from "vue";
import { CheckCircle2, Clock3, GitCompareArrows } from "lucide-vue-next";
import type { NegotiationSummary } from "~/types/equipment";
import { formatNumber } from "~/utils/format";

const props = defineProps<{
  negotiation: NegotiationSummary;
}>();

const total = computed(
  () => props.negotiation.completed + props.negotiation.open,
);

const completionPercentage = computed(() => {
  if (!total.value) return 0;

  return (props.negotiation.completed / total.value) * 100;
});

const formattedPercentage = computed(() =>
  completionPercentage.value.toFixed(1).replace(".", ","),
);
</script>

<template>
  <DashboardCard
    title="Negociação"
    subtitle="Baseado na data de negociação registrada."
    :icon="CheckCircle2"
  >
    <div class="negotiation-body">
      <!-- Visão principal -->
      <section class="progress-summary">
        <div class="progress-header">
          <div class="progress-title">
            <strong>
              {{ formatNumber(negotiation.completed, 0) }}
              de
              {{ formatNumber(total, 0) }}
            </strong>

            <span>negociações concluídas</span>
          </div>

          <strong class="progress-percentage">
            {{ formattedPercentage }}%
          </strong>
        </div>

        <div
          class="progress-track"
          role="progressbar"
          :aria-valuenow="completionPercentage"
          aria-valuemin="0"
          aria-valuemax="100"
          :aria-label="`${formattedPercentage}% das negociações concluídas`"
        >
          <span
            class="progress-value"
            :style="{
              width: `${Math.min(completionPercentage, 100)}%`,
            }"
          />
        </div>
      </section>

      <!-- Situação operacional -->
      <div class="status-grid">
        <div class="status-card">
          <div class="status-icon">
            <Clock3 :size="17" />
          </div>

          <div class="status-content">
            <span class="status-label"> Em aberto </span>

            <strong>
              {{ formatNumber(negotiation.open, 0) }}
            </strong>

            <small> Ainda não concluídas </small>
          </div>
        </div>

        <div class="status-card">
          <div class="status-icon">
            <GitCompareArrows :size="17" />
          </div>

          <div class="status-content">
            <span class="status-label"> Em negociação </span>

            <strong>
              {{ formatNumber(negotiation.inNegotiation, 0) }}
            </strong>

            <small> Negociação / equalização </small>
          </div>
        </div>
      </div>
    </div>
  </DashboardCard>
</template>

<style scoped>
.negotiation-body {
  display: flex;
  height: 100%;
  flex-direction: column;
  gap: 22px;
}

/* =========================================================
   PROGRESSO PRINCIPAL
   ========================================================= */

.progress-summary {
  display: grid;
  gap: 12px;
}

.progress-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
}

.progress-title {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.progress-title strong {
  color: #213957;
  font-size: 20px;
  font-weight: 750;
  line-height: 1.1;
}

.progress-title span {
  color: #8490a2;
  font-size: 11px;
  font-weight: 500;
}

.progress-percentage {
  color: #568d43;
  font-size: 18px;
  font-weight: 750;
  line-height: 1;
}

.progress-track {
  width: 100%;
  height: 9px;

  overflow: hidden;

  border-radius: 999px;

  background: #edf1f5;
}

.progress-value {
  display: block;
  height: 100%;

  border-radius: inherit;

  background: #5c924a;

  transition: width 0.25s ease;
}

/* =========================================================
   STATUS
   ========================================================= */

.status-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.status-card {
  display: flex;
  min-width: 0;
  align-items: flex-start;
  gap: 10px;

  padding: 13px;

  border: 1px solid #e4e9f0;
  border-radius: 9px;

  background: #fafbfd;
}

.status-icon {
  display: grid;
  width: 31px;
  height: 31px;
  flex: 0 0 31px;
  place-items: center;

  border-radius: 8px;

  background: #edf2f8;
  color: #526b8c;
}

.status-content {
  display: flex;
  min-width: 0;
  flex-direction: column;
}

.status-label {
  margin-bottom: 3px;

  color: #79869a;

  font-size: 9.5px;
  font-weight: 750;

  letter-spacing: 0.045em;
  text-transform: uppercase;
}

.status-content strong {
  color: #253c59;

  font-size: 20px;
  font-weight: 750;
  line-height: 1.1;
}

.status-content small {
  margin-top: 4px;

  color: #98a2b1;

  font-size: 10px;
  font-weight: 500;
}

/* =========================================================
   RESPONSIVIDADE
   ========================================================= */

@media (max-width: 620px) {
  .status-grid {
    grid-template-columns: 1fr;
  }

  .progress-header {
    align-items: flex-start;
  }
}
</style>
