<script setup lang="ts">
import { VProgressCircular } from "vuetify/components";

const props = withDefaults(defineProps<{
  title: string;
  subtitle: string;
  loading?: boolean;
  empty?: boolean;
  emptyText?: string;
  note?: string;
}>(), {
  loading: false,
  empty: false,
  emptyText: "Ainda não há dados suficientes para esta visualização.",
  note: "",
});
</script>

<template>
  <section class="surface chart-frame" :aria-busy="props.loading || undefined">
    <header class="frame-head">
      <div>
        <h2>{{ props.title }}</h2>
        <p>{{ props.subtitle }}</p>
      </div>
      <slot name="actions" />
    </header>
    <div class="frame-body">
      <div v-if="props.loading" class="frame-state" role="status">
        <VProgressCircular indeterminate color="primary" :size="30" :width="3" />
        <span>Carregando gráfico…</span>
      </div>
      <div v-else-if="props.empty" class="frame-state frame-state--empty" role="status">
        {{ props.emptyText }}
      </div>
      <slot v-else />
    </div>
    <footer v-if="props.note" class="frame-note">{{ props.note }}</footer>
  </section>
</template>

<style scoped>
.chart-frame { display: flex; flex-direction: column; min-width: 0; overflow: hidden; }
.frame-head { display: flex; align-items: start; justify-content: space-between; gap: 12px; padding: 20px 20px 10px; }
.frame-head h2 { margin: 0; font-size: 15px; font-weight: 800; line-height: 1.45; color: #213758; }
.frame-head p { margin: 3px 0 0; color: #7d8a9d; font-size: 11.5px; line-height: 1.5; }
.frame-body { min-width: 0; flex: 1; padding: 7px 15px 15px; }
.frame-state { min-height: 265px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 12px; color: #8290a3; font-size: 12px; text-align: center; padding: 18px; }
.frame-state--empty { background: #fafbfd; border: 1px dashed #e2e8f0; border-radius: 10px; margin: 5px; min-height: 225px; }
.frame-note { border-top: 1px solid #edf1f5; padding: 10px 20px 13px; color: #8896a8; font-size: 10.5px; line-height: 1.5; }
</style>
