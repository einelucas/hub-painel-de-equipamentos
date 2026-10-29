<script setup lang="ts">
import { mdiFileUploadOutline } from "@mdi/js";
import { VBtn } from "vuetify/components";
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
      variant="text"
      size="small"
      aria-label="Importar equipamentos"
      title="Importar equipamentos"
      data-testid="nav-import"
      :icon="mdiFileUploadOutline"
      @click="open = true"
    />
    <ImportEquipmentModal :open="open" :unit-id="context.selectedUnit" @close="open = false" />
  </template>
</template>
