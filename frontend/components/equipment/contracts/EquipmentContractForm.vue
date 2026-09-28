<script setup lang="ts">
import { reactive, ref } from "vue";
import { Upload } from "lucide-vue-next";
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
const fileInput = ref<HTMLInputElement | null>(null);
const pendingFile = ref<File | null>(null);

function pickFile(): void {
  fileInput.value?.click();
}

function onFileChosen(event: Event): void {
  const target = event.target as HTMLInputElement;
  pendingFile.value = target.files?.[0] ?? null;
}

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
      ><input v-model="form.contractNumber" maxlength="80"
    /></label>
    <label class="field"
      ><span>Data de escrituração</span
      ><input v-model="form.executedAt" type="date"
    /></label>
    <label class="field">
      <span>Arquivo do contrato</span>
      <button type="button" class="btn file-picker" @click="pickFile">
        <Upload :size="14" />
        {{
          pendingFile
            ? pendingFile.name
            : (contract?.file?.fileName ?? "Selecionar arquivo")
        }}
      </button>
      <input
        ref="fileInput"
        type="file"
        class="hidden-input"
        @change="onFileChosen"
      />
    </label>
    <p v-if="error" class="notice error" role="alert">
      {{ error }}
    </p>
    <div class="form-actions">
      <button type="button" class="btn" @click="emit('cancel')">Cancelar</button>
      <button type="submit" class="btn primary" :disabled="busy">
        {{ busy ? "Salvando..." : "Salvar" }}
      </button>
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
.file-picker {
  justify-content: flex-start;
  gap: 7px;
}
.hidden-input {
  display: none;
}
.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 9px;
}
</style>
