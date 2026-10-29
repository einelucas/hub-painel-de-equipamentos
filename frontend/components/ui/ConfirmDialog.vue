<script setup lang="ts">
import { computed, ref } from "vue";
import { mdiAlertOutline, mdiInformationOutline, mdiDeleteOutline, mdiClose } from "@mdi/js";
import { VDialog, VCard, VCardTitle, VCardText, VCardActions, VBtn, VIcon } from "vuetify/components";
import { useConfirm } from "~/composables/useConfirm";

const { state, accept, cancel } = useConfirm();

const dialogOpen = computed({
  get: () => state.open,
  set: (open: boolean) => {
    if (!open) cancel();
  },
});
const dialogIcon = computed(() => {
  if (state.icon === "trash") return mdiDeleteOutline;
  if (state.icon === "warning") return mdiAlertOutline;
  return mdiInformationOutline;
});
const cancelButton = ref<InstanceType<typeof VBtn> | null>(null);

function focusCancel(): void {
  (cancelButton.value?.$el as HTMLElement | undefined)?.focus();
}
</script>

<template>
  <VDialog
    v-model="dialogOpen"
    max-width="440"
    aria-labelledby="confirm-dialog-title"
    aria-describedby="confirm-dialog-message"
    @after-enter="focusCancel"
  >
    <VCard class="confirm-card" rounded="lg">
      <VCardTitle class="confirm-head">
        <h2 id="confirm-dialog-title">{{ state.title }}</h2>
        <VBtn
          type="button"
          variant="text"
          :icon="mdiClose"
          aria-label="Fechar"
          density="comfortable"
          @click="cancel"
        />
      </VCardTitle>
      <VCardText class="confirm-body">
        <VIcon :icon="dialogIcon" size="28" :color="state.tone === 'danger' ? 'error' : 'primary'" aria-hidden="true" />
        <div class="confirm-copy">
          <p id="confirm-dialog-message">{{ state.message }}</p>
          <p v-if="state.detail" class="confirm-detail">{{ state.detail }}</p>
        </div>
      </VCardText>
      <VCardActions class="confirm-actions">
        <VBtn
          ref="cancelButton"
          type="button"
          class="confirm-btn--cancel"
          variant="outlined"
          color="primary"
          rounded="lg"
          @click="cancel"
        >
          {{ state.cancelLabel }}
        </VBtn>
        <VBtn
          type="button"
          :class="state.tone === 'danger' ? 'confirm-btn--danger' : 'confirm-btn--primary'"
          variant="tonal"
          :color="state.tone === 'danger' ? 'error' : 'primary'"
          rounded="lg"
          @click="accept"
        >
          {{ state.confirmLabel }}
        </VBtn>
      </VCardActions>
    </VCard>
  </VDialog>
</template>

<style scoped>
.confirm-card { padding: 4px; color: #1f3352; }
.confirm-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 16px;
  white-space: normal;
}
.confirm-head h2 {
  margin: 0;
  color: #1f3352;
  font-size: 19px;
  font-weight: 800;
  letter-spacing: -0.01em;
}
.confirm-body { display: flex; align-items: flex-start; gap: 14px; padding: 12px 16px; }
.confirm-copy { display: grid; min-width: 0; gap: 7px; }
.confirm-copy p { margin: 0; }
#confirm-dialog-message { color: #46566d; font-size: 14px; font-weight: 600; line-height: 1.45; }
.confirm-detail { color: #7c8a9e; font-size: 12px; line-height: 1.5; }
.confirm-actions { display: flex; justify-content: flex-end; gap: 10px; padding: 12px 16px; }
@media (max-width: 480px) {
  .confirm-actions { flex-direction: column-reverse; align-items: stretch; }
}
</style>
