<script setup lang="ts">
/**
 * Ponto único de teleporte dos diálogos. Em produção o conteúdo vai para o
 * `body`; nos testes o componente é substituído por um stub que mantém o
 * conteúdo dentro da árvore montada, onde as asserções conseguem alcançá-lo.
 */
withDefaults(defineProps<{ to?: string }>(), { to: "body" });
</script>

<template>
  <Teleport :to="to">
    <slot />
  </Teleport>
</template>
