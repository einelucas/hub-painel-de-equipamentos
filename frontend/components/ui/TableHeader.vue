<script setup lang="ts">
import { VProgressLinear } from "vuetify/components";
import { cn } from "~/utils/cn";

const props = defineProps<{ class?: string; loading?: boolean; loadingLabel?: string }>();
</script>

<template>
  <thead data-slot="table-header" :class="cn('bg-muted/60 [&_tr]:border-b', props.class)">
    <slot />
    <tr v-if="props.loading" class="table-progress-row">
      <th colspan="100" class="table-progress-cell">
        <VProgressLinear
          color="primary"
          indeterminate
          height="3"
          :aria-label="props.loadingLabel ?? 'Carregando dados da tabela'"
        />
      </th>
    </tr>
  </thead>
</template>

<style scoped>
.table-progress-row { border: 0 !important; }
.table-progress-cell {
  height: 3px;
  padding: 0 !important;
  border: 0;
  background: transparent;
  line-height: 0;
}
</style>
