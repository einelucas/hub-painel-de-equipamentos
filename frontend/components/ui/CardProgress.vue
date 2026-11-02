<script setup lang="ts">
import { VProgress } from "vuetify/components";

/**
 * Barra indeterminada no topo de um card enquanto ele carrega.
 * Decorativa (aria-hidden): o anúncio de carregamento fica no container com
 * role="status"/aria-busy — um progressbar por card poluiria o leitor de tela.
 * O card precisa de position: relative (e overflow: hidden p/ os cantos).
 */
</script>

<template>
  <VProgress
    class="card-progress"
    color="primary"
    indeterminate
    aria-hidden="true"
  />
</template>

<style scoped>
.card-progress {
  position: absolute;
  top: 0;
  right: 0;
  left: 0;
  z-index: 1;
  pointer-events: none;
}
</style>
