<script setup lang="ts">
import { computed, nextTick, ref, useId, watch } from "vue";
import { mdiClose } from "@mdi/js";
import { VDialog, VCard, VCardTitle, VCardText, VCardActions, VBtn } from "vuetify/components";

/**
 * Um único overlay nativo do Vuetify para os formulários do Hub.
 * O contrato de AppModal permanece estável para os seus consumidores.
 * VDialog gerencia o foco, o empilhamento, o Teleport e o bloqueio de rolagem.
 */
const props = withDefaults(
  defineProps<{
    open: boolean;
    title: string;
    size?: "default" | "wide";
    contained?: boolean;
    busy?: boolean;
    dismissableMask?: boolean;
    closeOnEscape?: boolean;
  }>(),
  {
    size: "default",
    contained: false,
    busy: false,
    dismissableMask: true,
    closeOnEscape: true,
  },
);
const emit = defineEmits<{ close: [] }>();
const titleId = `app-modal-title-${useId()}`;
const bodyEl = ref<HTMLElement | null>(null);

const dialogOpen = computed({
  get: () => props.open,
  set: (open: boolean) => {
    if (!open && !props.busy) emit("close");
  },
});

// Configuração conservadora para fluxos que explicitamente proíbem dismissal.
const persistent = computed(
  () => props.busy || !props.dismissableMask || !props.closeOnEscape,
);

function requestClose(): void {
  if (!props.busy) emit("close");
}

function focusFirstField(): void {
  bodyEl.value
    ?.querySelector<HTMLElement>(
      'input:not([disabled]):not([type="hidden"]), textarea:not([disabled]), select:not([disabled]), [tabindex="0"]',
    )
    ?.focus();
}

watch(
  () => props.open,
  async (open) => {
    if (!open) return;
    await nextTick();
    focusFirstField();
  },
  { flush: "post" },
);
</script>

<template>
  <VDialog
    v-if="open"
    v-model="dialogOpen"
    :persistent="persistent"
    :max-width="size === 'wide' ? 1040 : 680"
    :aria-labelledby="titleId"
    class="app-modal-overlay"
    @after-enter="focusFirstField"
  >
    <VCard
      class="modal-card"
      :class="{ 'modal-card--contained': contained }"
      rounded="lg"
    >
      <VCardTitle class="modal-header">
        <h2 :id="titleId">{{ title }}</h2>
        <VBtn
          class="modal-close"
          type="button"
          variant="text"
          color="secondary"
          density="comfortable"
          :icon="mdiClose"
          aria-label="Fechar"
          :disabled="busy"
          @click="requestClose"
        />
      </VCardTitle>
      <VCardText ref="bodyEl" class="modal-body">
        <slot />
      </VCardText>
      <VCardActions v-if="$slots.actions" class="modal-actions">
        <slot name="actions" />
      </VCardActions>
    </VCard>
  </VDialog>
</template>

<style scoped>
.modal-card {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
  max-height: calc(100dvh - 40px);
  border: 1px solid #e1e8f1;
  color: #1f3352;
}
.modal-card--contained { height: min(820px, calc(100dvh - 40px)); }
.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 17px 20px 15px;
  border-bottom: 1px solid #e9edf2;
  white-space: normal;
}
.modal-header h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 800;
  letter-spacing: -0.01em;
  line-height: 1.3;
}
.modal-close { flex: 0 0 auto; }
.modal-body {
  min-height: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
  padding: 20px;
}
.modal-card--contained .modal-body { overflow: hidden; padding-bottom: 0; }
.modal-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 9px;
  padding: 14px 20px 16px;
  background: #fbfcfe;
  border-top: 1px solid #e9edf2;
}
@media (max-width: 640px) {
  .modal-card { max-height: calc(100dvh - 24px); }
  .modal-card--contained { height: calc(100dvh - 24px); }
  .modal-header { padding: 15px 17px 13px; }
  .modal-body { padding: 16px 20px 20px; }
  .modal-actions { padding: 13px 17px 15px; }
}
</style>
