<script setup lang="ts">
import { stageTone } from "~/utils/stages";

defineProps<{ stage: number; name: string }>();
</script>

<template>
  <span class="stage-badge" :class="stageTone(stage)">{{ stage }} · {{ name }}</span>
</template>

<style scoped>
.stage-badge { display: inline-flex; white-space: nowrap; border-radius: 999px; padding: 4px 8px; font-size: 11px; font-weight: 750; }
.stage-badge--new { background: #eef2f7; color: #53647a; }
.stage-badge--progress { background: #fff3df; color: #9b6418; }
.stage-badge--advanced { background: #e8f1fc; color: #2f5f9c; }
.stage-badge--complete { background: #eaf4e5; color: #477a32; }
</style>
