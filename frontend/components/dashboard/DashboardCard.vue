<script setup lang="ts">
import type { Component } from "vue";
import CardProgress from "~/components/ui/CardProgress.vue";

withDefaults(
  defineProps<{
    title: string;
    subtitle?: string;
    icon?: Component;
    loading?: boolean;
  }>(),
  { subtitle: "", icon: undefined, loading: false },
);
</script>

<template>
  <section class="surface dashboard-card" :aria-busy="loading || undefined">
    <CardProgress v-if="loading" />
    <div class="surface-header">
      <div>
        <h2><component :is="icon" v-if="icon" :size="15" /> {{ title }}</h2>
        <p v-if="subtitle">{{ subtitle }}</p>
      </div>
    </div>
    <div class="surface-body dashboard-card-body">
      <slot />
    </div>
  </section>
</template>

<style scoped>
/* Estrutura visual comum aos cards do dashboard (Negociação, Situação de
   prazos, Próxima startup) — o conteúdo específico de cada um vem só pelo
   slot padrão; nenhum CSS estrutural é duplicado entre eles. */
.dashboard-card {
  display: flex;
  flex-direction: column;
  height: 100%;
  /* Relativo + sem transbordo: a barra no topo acompanha os cantos arredondados. */
  position: relative;
  overflow: hidden;
}
.dashboard-card .surface-header h2 {
  display: inline-flex;
  align-items: center;
  gap: 7px;
}
.dashboard-card-body {
  flex: 1;
  min-height: 0;
}
</style>
