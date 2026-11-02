<script setup lang="ts">
import { mdiDeleteOutline } from "@mdi/js";
import { computed, reactive, ref } from "vue";
import { VBtn } from "vuetify/components";
import FilePicker from "~/components/ui/FilePicker.vue";
import UploadProgress from "~/components/ui/UploadProgress.vue";
import type { Contract } from "~/types/equipment";

export interface EquipmentContractFormValues {
  contractNumber: string;
  executedAt: string;
  file: File | null;
}

/** `contract` nulo = criação. O modal só monta o formulário quando aberto,
 * então os campos partem sempre do contrato recebido. */
const props = defineProps<{
  contract: Contract | null;
  busy: boolean;
  /** Fase do container: salvando o contrato, enviando ou removendo o anexo. */
  phase?: "saving" | "uploading" | "removing-file" | null;
  /** Progresso do envio do anexo (null = total desconhecido). */
  uploadPercent?: number | null;
  error: string;
}>();
const emit = defineEmits<{
  submit: [values: EquipmentContractFormValues];
  "remove-file": [];
  cancel: [];
}>();

const form = reactive({
  contractNumber: props.contract?.contractNumber ?? "",
  executedAt: props.contract?.executedAt ?? "",
});
const pendingFile = ref<File | null>(null);

/** O anexo sobe depois que o contrato é salvo; enquanto isso o modal mostra
 * a fase separada com o progresso do envio. */
const uploading = computed(() => props.phase === "uploading");
const uploadKnownPercent = computed(() =>
  typeof props.uploadPercent === "number" ? props.uploadPercent : null,
);
const busyLabel = computed(() => {
  if (uploading.value) return "Enviando arquivo...";
  if (props.phase === "removing-file") return "Removendo arquivo...";
  return "Salvando...";
});

function submit(): void {
  emit("submit", {
    contractNumber: form.contractNumber,
    executedAt: form.executedAt,
    file: pendingFile.value,
  });
}
</script>

<template>
  <form class="item-form" @submit.prevent="submit">
    <div class="field">
      <VTextField v-model="form.contractNumber" label="Número do contrato" maxlength="80" :disabled="props.busy" />
    </div>
    <div class="field">
      <VTextField v-model="form.executedAt" label="Data de escrituração" type="date" :disabled="props.busy" />
    </div>
    <div class="field">
      <span>Arquivo do contrato</span>
      <div class="attachment-actions">
        <FilePicker
          v-model="pendingFile"
          :current-label="props.contract?.file?.fileName ?? ''"
          label="Selecionar arquivo"
          :disabled="props.busy"
        />
        <VBtn
          v-if="props.contract?.file"
          type="button"
          variant="text"
          color="error"
          :prepend-icon="mdiDeleteOutline"
          :disabled="props.busy"
          data-testid="remove-contract-file"
          @click="emit('remove-file')"
        >
          Remover anexo
        </VBtn>
      </div>
    </div>

    <UploadProgress
      v-if="uploading"
      :uploading="uploadKnownPercent === null || uploadKnownPercent < 100"
      :percent="uploadKnownPercent"
      upload-label="Enviando arquivo do contrato"
      processing-label="Registrando o arquivo no servidor"
      test-id="contract-upload-progress"
    />

    <VAlert v-if="error" class="notice error" type="error" role="alert">
      {{ error }}
    </VAlert>
    <div class="form-actions">
      <VBtn variant="outlined" color="secondary" :disabled="props.busy" @click="emit('cancel')">Cancelar</VBtn>
      <VBtn
        type="submit"
        variant="flat"
        color="primary"
        :loading="props.busy"
       :disabled="props.busy">
        {{ props.busy ? busyLabel : "Salvar" }}
      </VBtn>
    </div>
  </form>
</template>

<style scoped>
.item-form {
  display: grid;
  gap: 14px;
}
.field {
  display: grid;
  gap: 4px;
  font-size: 12px;
}
.field span {
  color: #7a879a;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}
.field input {
  border: 1px solid #d8dee7;
  border-radius: 6px;
  padding: 7px 9px;
  font-size: 13px;
}
.attachment-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  min-width: 0;
}
.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 9px;
}
</style>
