<script setup lang="ts">
import { computed } from "vue";
import { criticalityColor, translucentBadgeStyle } from "~/utils/catalogColors";

const props = defineProps<{ label: string; color?: string | null }>();
const style = computed(() => translucentBadgeStyle(criticalityColor(props.label, props.color)));
</script>

<template>
  <span class="criticality-badge" :style="style" :title="label" data-testid="criticality-badge">{{ label }}</span>
</template>

<style scoped>
.criticality-badge { display: inline-flex; width: 112px; min-height: 26px; align-items: center; justify-content: center; box-sizing: border-box; border: 1px solid var(--badge-border); border-radius: 999px; padding: 4px 9px; background: var(--badge-background); color: #263b59; font-size: 10.5px; font-weight: 800; line-height: 1.15; text-align: center; }
</style>
