<script setup lang="ts">
/**
 * `wide`: fluxos com tabelas e mapeamentos lado a lado (ex.: importação).
 * `contained`: altura fixa e o próprio conteúdo decide o que rola (ex.: painel
 * com índice lateral fixo); sem ele, o modal inteiro rola.
 */
withDefaults(
  defineProps<{ open: boolean; title: string; size?: "default" | "wide"; contained?: boolean }>(),
  { size: "default", contained: false },
);
const emit = defineEmits<{ close: [] }>();
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="modal-backdrop" role="dialog" aria-modal="true" @click.self="emit('close')">
      <section class="modal-card" :class="{ 'modal-card--wide': size === 'wide', 'modal-card--contained': contained }">
        <header class="modal-header"><h2>{{ title }}</h2><button class="btn small" @click="emit('close')">Fechar</button></header>
        <div class="modal-body"><slot /></div>
        <footer v-if="$slots.actions" class="modal-actions"><slot name="actions" /></footer>
      </section>
    </div>
  </Teleport>
</template>
