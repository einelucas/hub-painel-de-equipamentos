<script setup lang="ts">
import { computed, reactive, ref } from "vue";
import Button from "~/components/ui/Button.vue";
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
  /** Fase do container: salvando o contrato ou enviando o anexo. */
  phase?: "saving" | "uploading" | null;
  /** Progresso do envio do anexo (null = total desconhecido). */
  uploadPercent?: number | null;
  error: string;
}>();
const emit = defineEmits<{
  submit: [values: EquipmentContractFormValues];
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
const busyLabel = computed(() => (uploading.value ? "Enviando arquivo..." : "Salvando..."));

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
    <label class="field"
      ><span>Número do contrato</span
      ><input v-model="form.contractNumber" maxlength="80" :disabled="props.busy"
    /></label>
    <label class="field"
      ><span>Data de escrituração</span
      ><input v-model="form.executedAt" type="date" :disabled="props.busy"
    /></label>
    <label class="field">
      <span>Arquivo do contrato</span>
      <FilePicker
        v-model="pendingFile"
        :current-label="props.contract?.file?.fileName ?? ''"
        label="Selecionar arquivo"
        :disabled="props.busy"
      />
    </label>

    <UploadProgress
      v-if="uploading"
      :uploading="uploadKnownPercent === null || uploadKnownPercent < 100"
      :percent="uploadKnownPercent"
      upload-label="Enviando arquivo do contrato"
      processing-label="Registrando o arquivo no servidor"
      test-id="contract-upload-progress"
    />

    <p v-if="error" class="notice error" role="alert">
      {{ error }}
    </p>
    <div class="form-actions">
      <Button variant="outline" :disabled="props.busy" @click="emit('cancel')">Cancelar</Button>
      <Button
        type="submit"
        variant="default"
        :loading="props.busy"
      >
        {{ props.busy ? busyLabel : "Salvar" }}
      </Button>
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
.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 9px;
}
</style>
