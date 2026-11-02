<script setup lang="ts">
import CardProgress from "~/components/ui/CardProgress.vue";

withDefaults(
  defineProps<{
    label: string;
    value: string;
    detail?: string;
    tone?: "default" | "good" | "bad";
    loading?: boolean;
  }>(),
  {
    detail: "",
    tone: "default",
    loading: false,
  },
);
</script>

<template>
  <article class="metric-card" :class="tone" :aria-busy="loading || undefined">
    <CardProgress v-if="loading" />
    <div class="label">{{ label }}</div>
    <div class="value">{{ value }}</div>
    <div v-if="detail" class="detail">{{ detail }}</div>
  </article>
</template>

<style scoped>
/* Relativo + sem transbordo: a barra no topo acompanha os cantos arredondados. */
.metric-card {
  position: relative;
  overflow: hidden;
}
</style>
