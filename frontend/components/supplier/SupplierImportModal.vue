<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { FileSpreadsheet } from "lucide-vue-next";
import AppModal from "~/components/ui/AppModal.vue";
import type { SupplierImportResult } from "~/types/equipment";

/** Importa planilha de fornecedores: atualiza existentes e adiciona novos, sem remover. */
const props = defineProps<{ open: boolean }>();
const emit = defineEmits<{ close: []; imported: [result: SupplierImportResult] }>();

const api = useApi();
const file = ref<File | null>(null);
const uploading = ref(false);
const error = ref("");
const result = ref<SupplierImportResult | null>(null);
const uploadPercent = ref(0);
const elapsedSeconds = ref(0);
let timer: ReturnType<typeof setInterval> | null = null;

/** "upload" enquanto os bytes sobem; "processing" até a resposta do servidor. */
const phase = computed<"idle" | "upload" | "processing">(() => {
  if (!uploading.value) return "idle";
  return uploadPercent.value >= 100 ? "processing" : "upload";
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

function stopTimer(): void {
  if (timer) clearInterval(timer);
  timer = null;
}

onBeforeUnmount(stopTimer);

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

function pick(event: Event): void {
  file.value = (event.target as HTMLInputElement).files?.[0] ?? null;
  error.value = "";
}

async function submit(): Promise<void> {
  if (!file.value || uploading.value) return;
  uploading.value = true;
  uploadPercent.value = 0;
  elapsedSeconds.value = 0;
  stopTimer();
  timer = setInterval(() => { elapsedSeconds.value += 1; }, 1000);
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
    stopTimer();
    uploading.value = false;
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
      <label class="field">
        <span>Planilha</span>
        <input type="file" accept=".xlsx" data-testid="supplier-import-file" :disabled="uploading" @change="pick">
      </label>
      <p v-if="file" class="file-info" data-testid="supplier-import-file-info">
        <FileSpreadsheet :size="16" aria-hidden="true" />
        <span class="file-name">{{ file.name }}</span>
        <span class="file-size">{{ formatSize(file.size) }}</span>
      </p>

      <div v-if="uploading" class="progress-box" data-testid="supplier-import-progress">
        <p class="status" role="status" aria-live="polite" data-testid="supplier-import-status">
          <template v-if="phase === 'upload'">Enviando planilha… {{ uploadPercent }}%</template>
          <template v-else>
            Processando planilha no servidor…
            <span data-testid="supplier-import-elapsed">{{ elapsedSeconds }}s</span>
          </template>
        </p>
        <div
          v-if="phase === 'upload'"
          class="bar"
          role="progressbar"
          aria-label="Progresso do envio"
          aria-valuemin="0"
          aria-valuemax="100"
          :aria-valuenow="uploadPercent"
          data-testid="supplier-import-bar"
        >
          <span class="bar-fill" :style="{ width: `${uploadPercent}%` }" />
        </div>
        <div
          v-else
          class="bar indeterminate"
          role="progressbar"
          aria-label="Processando no servidor"
          data-testid="supplier-import-bar"
        >
          <span class="bar-fill" />
        </div>
        <p class="warn">Não feche esta janela até a importação terminar.</p>
      </div>

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
        <button type="button" class="btn" :disabled="uploading" @click="requestClose">Fechar</button>
        <button type="submit" class="btn primary" :disabled="!file || uploading" data-testid="supplier-import-submit">
          <span v-if="uploading" class="spinner spinner-small" /> {{ submitLabel }}
        </button>
      </div>
    </form>
  </AppModal>
</template>

<style scoped>
.supplier-import { display: grid; gap: 14px; }
.hint { margin: 0; color: var(--muted, #6b7a8f); font-size: 12.5px; line-height: 1.5; }
.hint code { font-family: var(--mono, monospace); font-size: 11.5px; }
.file-info { display: flex; align-items: center; gap: 8px; margin: 0; font-size: 12.5px; }
.file-name { font-weight: 700; overflow-wrap: anywhere; }
.file-size { color: var(--muted, #6b7a8f); }
.progress-box { display: grid; gap: 8px; border: 1px solid var(--rule, #dde5ef); border-radius: 10px; padding: 12px 14px; }
.status { margin: 0; font-size: 12.5px; font-weight: 700; }
.warn { margin: 0; color: var(--muted, #6b7a8f); font-size: 11.5px; }
.bar { position: relative; height: 8px; overflow: hidden; border-radius: 999px; background: #e4eaf2; }
.bar-fill { display: block; height: 100%; border-radius: 999px; background: #304f7e; transition: width 0.2s ease; }
.indeterminate .bar-fill { position: absolute; width: 35%; animation: import-slide 1.2s ease-in-out infinite; }
@keyframes import-slide { from { left: -35%; } to { left: 100%; } }
@media (prefers-reduced-motion: reduce) {
  .bar-fill { transition: none; }
  .indeterminate .bar-fill { width: 100%; animation: none; opacity: 0.55; }
  .spinner-small { animation: none; }
}
.error { margin: 0; color: var(--stop, #a4453a); font-size: 12px; font-weight: 700; }
.result { border: 1px solid var(--rule, #dde5ef); border-radius: 10px; padding: 12px 14px; font-size: 12.5px; }
.result > ul { display: flex; flex-wrap: wrap; gap: 6px 18px; margin: 0; padding: 0; list-style: none; }
.total { margin: 8px 0 0; color: var(--muted, #6b7a8f); font-size: 11.5px; }
.errors { max-height: 180px; margin: 10px 0 0; padding: 0 0 0 16px; overflow-y: auto; color: var(--stop, #a4453a); }
.actions { display: flex; justify-content: flex-end; gap: 8px; }
</style>
