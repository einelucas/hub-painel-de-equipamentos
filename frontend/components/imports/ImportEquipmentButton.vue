<script setup lang="ts">
import { computed, ref } from "vue";
import { FileUp } from "lucide-vue-next";

/**
 * Ação da barra do módulo: abre o wizard de importação (não é rota de navegação).
 * Visível só com `equipments:write`; o backend nega de qualquer forma.
 */
const auth = useAuthStore();
const context = useModuleContextStore();
const canImport = computed(() => auth.can("equipments:write"));
const open = ref(false);
</script>

<template>
  <template v-if="canImport">
    <button
      type="button"
      class="module-action"
      aria-label="Importar equipamentos"
      data-testid="nav-import"
      @click="open = true"
    >
      <FileUp :size="18" aria-hidden="true" />
      <span class="module-action-tip" aria-hidden="true">Importar equipamentos</span>
    </button>
    <ImportEquipmentModal :open="open" :unit-id="context.selectedUnit" @close="open = false" />
  </template>
</template>

<style scoped>
/* Mesma geometria dos itens da TabsNav (42px, raio 12px) para não alterar a altura da barra. */
.module-action { position: relative; display: inline-flex; flex: 0 0 auto; width: 42px; height: 42px; align-items: center; justify-content: center; border: 1px solid transparent; border-radius: 12px; background: transparent; color: #5d6b80; transition: background .15s, color .15s; }
.module-action:hover { background: #f2f6fb; color: #2b3e58; }
.module-action:focus-visible { outline: 2px solid #304f7e; outline-offset: 2px; }
.module-action-tip { position: absolute; top: calc(100% + 9px); left: 50%; z-index: 30; border-radius: 9px; padding: 5px 10px; background: #2b3e58; color: #fff; font-size: 11.5px; font-weight: 700; white-space: nowrap; opacity: 0; pointer-events: none; transform: translate(-50%, -3px); transition: opacity .14s ease, transform .14s ease; }
.module-action-tip::before { position: absolute; bottom: 100%; left: 50%; border: 5px solid transparent; border-bottom-color: #2b3e58; content: ""; transform: translateX(-50%); }
.module-action:hover .module-action-tip, .module-action:focus-visible .module-action-tip { opacity: 1; transform: translate(-50%, 0); }
@media (prefers-reduced-motion: reduce) { .module-action-tip { transition: none; } }
</style>
