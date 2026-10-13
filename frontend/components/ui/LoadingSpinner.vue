<script setup lang="ts">
const props = withDefaults(defineProps<{ size?: "sm" | "md"; label?: string }>(), { size: "md", label: undefined });
</script>

<template>
  <span class="loading-spinner" role="status" aria-live="polite">
    <span :class="props.size === 'sm' ? 'spinner-small' : 'spinner'" aria-hidden="true" />
    <span v-if="props.label" class="loading-spinner-label">{{ props.label }}</span>
  </span>
</template>

<style scoped>
.loading-spinner { display: inline-flex; align-items: center; gap: 8px; color: #748197; }
</style>
