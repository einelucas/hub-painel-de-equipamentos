<script setup lang="ts">
import { Loading } from "@element-plus/icons-vue";
import { ElIcon } from "element-plus";

/**
 * Spinner construído sobre o `ElIcon` do Element Plus (ícone `Loading`).
 * Os tamanhos seguem os antigos `.spinner`/`.spinner-small` do Hub
 * (28px/14px); os spinners dentro de botões continuam sendo CSS próprio.
 */
const props = withDefaults(defineProps<{ size?: "sm" | "md"; label?: string }>(), {
  size: "md",
  label: undefined,
});
</script>

<template>
  <span class="loading-spinner" role="status" aria-live="polite">
    <ElIcon
      class="is-loading"
      :size="props.size === 'sm' ? 14 : 28"
      aria-hidden="true"
    >
      <Loading />
    </ElIcon>
    <span v-if="props.label" class="loading-spinner-label">{{ props.label }}</span>
  </span>
</template>

<style scoped>
.loading-spinner { display: inline-flex; align-items: center; gap: 8px; color: #748197; }
@media (prefers-reduced-motion: reduce) {
  .is-loading { animation-duration: 2.4s; }
}
</style>
