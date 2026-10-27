<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { FileSpreadsheet } from "lucide-vue-next";
import AppModal from "~/components/ui/AppModal.vue";
import Button from "~/components/ui/Button.vue";
import FilePicker from "~/components/ui/FilePicker.vue";
import UploadProgress from "~/components/ui/UploadProgress.vue";
import type { SupplierImportResult } from "~/types/equipment";

/** Importa planilha de fornecedores: atualiza existentes e adiciona novos, sem remover. */
const props = defineProps<{ open: boolean }>();
const emit = defineEmits<{ close: []; imported: [result: SupplierImportResult] }>();

const api = useApi();
const file = ref<File | null>(null);
const uploading = ref(false);
const error = ref("");
const result = ref<SupplierImportResult | null>(null);
const uploadPercent = ref<number | null>(null);

/** Envio dos bytes (determinístico quando o total é conhecido) e, depois,
 * processamento no servidor (indeterminado). */
const phase = computed<"idle" | "upload" | "processing">(() => {
  if (!uploading.value) return "idle";
  return uploadPercent.value !== null && uploadPercent.value >= 100 ? "processing" : "upload";
});

const submitLabel = computed(() => {
  if (phase.value === "upload") return "Enviando…";
  if (phase.value === "processing") return "Processando…";
  return "Importar";
});

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1).replace(".", ",")} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1).replace(".", ",")} MB`;
}

/** Não fecha enquanto o envio/processamento está em andamento. */
function requestClose(): void {
  if (uploading.value) return;
  emit("close");
}

function onProgress(loaded: number, total: number): void {
  if (total > 0) uploadPercent.value = Math.min(100, Math.floor((loaded / total) * 100));
}

watch(() => props.open, (open) => {
  if (open) {
    file.value = null;
    error.value = "";
    result.value = null;
  }
});

async function submit(): Promise<void> {
  if (!file.value || uploading.value) return;
  uploading.value = true;
  uploadPercent.value = null;
  error.value = "";
  result.value = null;
  try {
    const form = new FormData();
    form.append("file", file.value, file.value.name);
    result.value = await api.upload<SupplierImportResult>("/suppliers/import", form, "POST", onProgress);
    emit("imported", result.value);
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "Não foi possível importar a planilha.";
  } finally {
    uploading.value = false;
    uploadPercent.value = null;
  }
}
</script>

<template>
  <AppModal :open="open" title="Importar planilha de fornecedores" @close="requestClose">
    <form class="supplier-import" data-testid="supplier-import" :aria-busy="uploading" @submit.prevent="submit">
      <p class="hint">
        Envie um arquivo .xlsx com as colunas
        <code>CODIGO_FORNECEDOR</code>, <code>NOME_FORNECEDOR</code>, <code>DOCUMENTO</code> e <code>ATIVO</code>.
        A importação atualiza existentes e adiciona novos; nenhum fornecedor é removido.
      </p>
      <div class="field">
        <span>Planilha</span>
        <FilePicker
          v-model="file"
          accept=".xlsx"
          label="Selecionar planilha"
          test-id="supplier-import-file"
          :disabled="uploading"
          @change="error = ''"
        />
      </div>
      <p v-if="file" class="file-info" data-testid="supplier-import-file-info">
        <FileSpreadsheet :size="16" aria-hidden="true" />
        <span class="file-name">{{ file.name }}</span>
        <span class="file-size">{{ formatSize(file.size) }}</span>
      </p>

      <UploadProgress
        v-if="uploading"
        :uploading="phase === 'upload'"
        :percent="phase === 'upload' ? uploadPercent : null"
        upload-label="Enviando planilha"
        processing-label="Processando planilha no servidor"
        warning="Não feche esta janela até a importação terminar."
        show-elapsed
        test-id="supplier-import-progress"
      />

      <p v-if="error" class="error" role="alert">{{ error }}</p>

      <div v-if="result" class="result" data-testid="supplier-import-result">
        <ul>
          <li><strong>{{ result.created }}</strong> criado(s)</li>
          <li><strong>{{ result.updated }}</strong> atualizado(s)</li>
          <li><strong>{{ result.unchanged }}</strong> sem alteração</li>
          <li><strong>{{ result.errors.length }}</strong> erro(s)</li>
        </ul>
        <p class="total">{{ result.total }} linha(s) processada(s).</p>
        <ul v-if="result.errors.length" class="errors" data-testid="supplier-import-errors">
          <li v-for="item in result.errors" :key="`${item.row}-${item.message}`">
            Linha {{ item.row }}: {{ item.message }}
          </li>
        </ul>
      </div>

      <div class="actions">
        <Button variant="outline" :disabled="uploading" @click="requestClose">Fechar</Button>
        <Button
          type="submit"
          variant="default"
          :loading="uploading"
          :disabled="!file"
          data-testid="supplier-import-submit"
        >
          {{ submitLabel }}
        </Button>
      </div>
    </form>
  </AppModal>
</template>

<style scoped>
.supplier-import { display: grid; gap: 14px; }
.hint { margin: 0; color: var(--muted, #6b7a8f); font-size: 12.5px; line-height: 1.5; }
.hint code { font-family: var(--mono, monospace); font-size: 11.5px; }
.field { display: grid; gap: 4px; font-size: 12px; }
.field span { color: #7a879a; font-size: 10px; font-weight: 800; letter-spacing: 0.05em; text-transform: uppercase; }
.file-info { display: flex; align-items: center; gap: 8px; margin: 0; font-size: 12.5px; }
.file-name { font-weight: 700; overflow-wrap: anywhere; }
.file-size { color: var(--muted, #6b7a8f); }
.error { margin: 0; color: var(--stop, #a4453a); font-size: 12px; font-weight: 700; }
.result { border: 1px solid var(--rule, #dde5ef); border-radius: 10px; padding: 12px 14px; font-size: 12.5px; }
.result > ul { display: flex; flex-wrap: wrap; gap: 6px 18px; margin: 0; padding: 0; list-style: none; }
.total { margin: 8px 0 0; color: var(--muted, #6b7a8f); font-size: 11.5px; }
.errors { max-height: 180px; margin: 10px 0 0; padding: 0 0 0 16px; overflow-y: auto; color: var(--stop, #a4453a); }
.actions { display: flex; justify-content: flex-end; gap: 8px; }
</style>
