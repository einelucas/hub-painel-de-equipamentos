<script setup lang="ts">
import { computed } from "vue";
import { stageBadgeStyle } from "~/utils/stages";

const props = defineProps<{ stage: number; name: string }>();

/** Cor oficial da fase (utils/stages), com o mesmo alfa dos demais badges. */
const style = computed(() => stageBadgeStyle(props.stage, props.name));
</script>

<template>
  <span class="stage-badge" :style="style">{{ stage }} · {{ name }}</span>
</template>

<style scoped>
.stage-badge { display: inline-flex; white-space: nowrap; border-radius: 999px; padding: 4px 8px; font-size: 11px; font-weight: 750; }
</style>
