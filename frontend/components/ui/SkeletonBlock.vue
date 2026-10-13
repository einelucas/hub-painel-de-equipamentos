<script setup lang="ts">
const props = withDefaults(defineProps<{ lines?: number; rows?: number }>(), { lines: 0, rows: 0 });
</script>

<template>
  <div class="skeleton-block" aria-hidden="true">
    <span v-for="n in props.lines" :key="`l${n}`" class="skeleton skeleton-line" :style="{ width: n === props.lines && props.lines > 1 ? '60%' : '100%' }" />
    <span v-for="n in props.rows" :key="`r${n}`" class="skeleton skeleton-row" />
  </div>
</template>
