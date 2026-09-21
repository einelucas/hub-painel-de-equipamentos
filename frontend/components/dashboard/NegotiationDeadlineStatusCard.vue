<script setup lang="ts">
import { computed } from "vue";
import { Hourglass } from "lucide-vue-next";
import type { NegotiationDeadlineStatusSummary } from "~/types/equipment";
import { negotiationDeadlineStatusDonut } from "~/utils/dashboard";
import { formatNumber } from "~/utils/format";

const props = defineProps<{ summary: NegotiationDeadlineStatusSummary }>();

const items = computed(() => negotiationDeadlineStatusDonut(props.summary));
</script>

<template>
  <DashboardCard
    title="Status dos prazos de negociação"
    subtitle="Distribuição das negociações conforme o prazo calculado."
    :icon="Hourglass"
  >
    <DonutChart :items="items" suffix="" :show-legend-values="true" />
    <p v-if="summary.notCalculable" class="not-calculable">
      Sem status calculável: <strong>{{ formatNumber(summary.notCalculable, 0) }}</strong>
    </p>
  </DashboardCard>
</template>

<style scoped>
.not-calculable { margin: 10px 0 0; color: #8b96a5; font-size: 11.5px; font-weight: 600; text-align: center; }
</style>
