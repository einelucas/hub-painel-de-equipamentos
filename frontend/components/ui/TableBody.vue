<script setup lang="ts">
import { computed } from "vue";
import { VSkeletonLoader } from "vuetify/components";
import { cn } from "~/utils/cn";

const props = withDefaults(defineProps<{
  class?: string;
  loading?: boolean;
  skeletonRows?: number;
  loadingLabel?: string;
}>(), {
  class: undefined,
  loading: false,
  skeletonRows: 6,
  loadingLabel: "Carregando linhas da tabela",
});

const skeletonType = computed(() => `table-row-divider@${props.skeletonRows}`);
</script>

<template>
  <tbody data-slot="table-body" :class="cn('[&_tr:last-child]:border-0', props.class)">
    <tr v-if="props.loading" class="table-skeleton-row">
      <td colspan="100" class="table-skeleton-cell">
        <VSkeletonLoader
          class="table-skeleton"
          :type="skeletonType"
          :aria-label="props.loadingLabel"
          data-testid="table-skeleton"
        />
      </td>
    </tr>
    <slot />
  </tbody>
</template>

<style scoped>
.table-skeleton-row { border: 0 !important; }
.table-skeleton-cell { padding: 0 !important; border: 0; }
.table-skeleton { width: 100%; background: transparent; }
</style>
