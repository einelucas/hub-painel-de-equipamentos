<script setup lang="ts">
import { mdiFileUploadOutline } from "@mdi/js";
import { VBtn, VIcon } from "vuetify/components";
import { computed, ref } from "vue";

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
    <VBtn
      type="button"
      class="module-action"
      variant="text"
      aria-label="Importar equipamentos"
      data-testid="nav-import"
      :icon="mdiFileUploadOutline"
      @click="open = true"
    >
      <VIcon :icon="mdiFileUploadOutline" size="18" aria-hidden="true" />
      <span class="module-nav-tip" aria-hidden="true">Importar equipamentos</span>
    </VBtn>
    <ImportEquipmentModal :open="open" :unit-id="context.selectedUnit" @close="open = false" />
  </template>
</template>
