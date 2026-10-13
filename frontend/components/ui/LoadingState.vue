<script setup lang="ts">
const props = withDefaults(defineProps<{ message?: string }>(), { message: "Carregando..." });
</script>

<template>
  <div class="loading-state-box" role="status" aria-live="polite" aria-busy="true">
    <span class="spinner" aria-hidden="true" />
    <slot>{{ props.message }}</slot>
  </div>
</template>

<style scoped>
.loading-state-box { display: flex; min-height: 220px; align-items: center; justify-content: center; gap: 12px; color: #748197; }
</style>
