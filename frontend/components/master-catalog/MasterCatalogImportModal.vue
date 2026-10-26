<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { Check, FileJson, Upload } from "lucide-vue-next";
import AppModal from "~/components/ui/AppModal.vue";
import Button from "~/components/ui/Button.vue";
import { useConfirm } from "~/composables/useConfirm";
import type { MasterCatalogSeedResult } from "~/types/masterCatalog";

const props = defineProps<{ open: boolean }>();
const emit = defineEmits<{
  close: [];
  imported: [result: MasterCatalogSeedResult];
}>();

const api = useApi();
const { confirm } = useConfirm();

const file = ref<File | null>(null);
const preview = ref<MasterCatalogSeedResult | null>(null);
const error = ref("");
const running = ref<"validate" | "apply" | "">("");
const fileInput = ref<HTMLInputElement | null>(null);
const busy = computed(() => running.value !== "");
const fileLabel = computed(() => {
  if (!file.value) return "Nenhum arquivo selecionado";
  const size = Math.max(1, Math.round(file.value.size / 1024));
  return `${file.value.name} · ${size} KB`;
});

watch(
  () => props.open,
  (open) => {
    if (!open) return;
    file.value = null;
    preview.value = null;
    error.value = "";
    running.value = "";
    if (fileInput.value) fileInput.value.value = "";
  },
  { immediate: true },
);

function requestClose(): void {
  if (busy.value) return;
  emit("close");
}

function onFileChange(event: Event): void {
  file.value = (event.target as HTMLInputElement).files?.[0] ?? null;
  preview.value = null;
  error.value = "";
}

async function execute(apply: boolean): Promise<boolean> {
  if (!file.value || busy.value) return false;
  running.value = apply ? "apply" : "validate";
  error.value = "";
  try {
    const payload = JSON.parse(await file.value.text()) as unknown;
    const result = await api.post<MasterCatalogSeedResult>(
      `/master-catalog/seed?dry_run=${!apply}`,
      payload,
    );
    if (apply) {
      emit("imported", result);
      emit("close");
    } else {
      preview.value = result;
    }
    return true;
  } catch (caught) {
    error.value =
      caught instanceof Error ? caught.message : "Seed inválido ou não foi possível processá-lo.";
    return false;
  } finally {
    running.value = "";
  }
}

function validate(): void {
  void execute(false);
}

async function apply(): Promise<void> {
  if (!preview.value || !file.value || busy.value) return;
  const confirmed = await confirm({
    title: "Aplicar catálogo",
    message: "Aplicar o seed no catálogo deste ambiente?",
    detail: "Os equipamentos de obras existentes não serão alterados.",
    confirmLabel: "Aplicar",
    tone: "primary",
    icon: "warning",
  });
  if (!confirmed) return;
  await execute(true);
}
</script>

<template>
  <AppModal
    :open="props.open"
    title="Importar seed do catálogo"
    :busy="busy"
    @close="requestClose"
  >
    <div class="import-flow">
      <p class="modal-intro">
        Importe um arquivo JSON do Catálogo Mestre no formato v2.1. A importação
        adiciona itens novos e preserva os existentes.
      </p>

      <label class="field">
        <span>Arquivo JSON *</span>
        <input
          ref="fileInput"
          type="file"
          accept=".json,application/json"
          :disabled="busy"
          @change="onFileChange"
        />
      </label>
      <p class="file-info">
        <FileJson :size="16" aria-hidden="true" />
        <span>{{ fileLabel }}</span>
      </p>

      <div class="import-actions">
        <Button
          variant="outline"
          size="sm"
          class="validate-button"
          :disabled="!file || busy"
          :loading="running === 'validate'"
          @click="validate"
        >
          <FileJson v-if="running !== 'validate'" aria-hidden="true" /> Validar arquivo
        </Button>
      </div>

      <p v-if="error" class="notice error" role="alert">{{ error }}</p>

      <section v-if="preview" class="preview" aria-live="polite">
        <div class="preview-head">
          <span class="preview-icon"><Check :size="16" aria-hidden="true" /></span>
          <div>
            <strong>Pré-validação concluída</strong>
            <p>Confira os totais antes de aplicar. Nada foi gravado ainda.</p>
          </div>
        </div>
        <div class="preview-grid">
          <div><strong>{{ preview.areasNew }}</strong><span>áreas novas</span></div>
          <div><strong>{{ preview.equipmentsNew }}</strong><span>equipamentos novos</span></div>
          <div><strong>{{ preview.componentsNew }}</strong><span>componentes novos</span></div>
          <div><strong>{{ preview.existing }}</strong><span>já existentes</span></div>
        </div>
        <Button
          size="sm"
          class="preview-apply"
          :disabled="busy || !file"
          :loading="running === 'apply'"
          @click="apply"
        >
          <Upload v-if="running !== 'apply'" aria-hidden="true" /> Aplicar ao catálogo
        </Button>
      </section>

      <p class="modal-note">
        O arquivo é processado apenas nesta ação e não fica armazenado no repositório
        público.
      </p>
    </div>

    <template #actions>
      <Button variant="outline" size="sm" :disabled="busy" @click="requestClose">
        Fechar
      </Button>
    </template>
  </AppModal>
</template>

<style scoped>
.import-flow {
  display: grid;
  gap: 14px;
}

.modal-intro,
.modal-note {
  margin: 0;
  color: #64748b;
  font-size: 12px;
  line-height: 1.55;
}

.modal-note {
  color: #8a96a7;
  font-size: 10.5px;
}

.file-info {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: -4px 0 0;
  overflow-wrap: anywhere;
  color: #7b8798;
  font-size: 11.5px;
}

.file-info svg {
  flex: 0 0 auto;
  color: #557aa8;
}

.import-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.preview {
  display: grid;
  gap: 12px;
  border: 1px solid #cfe3c9;
  border-radius: 11px;
  padding: 13px;
  background: #f8fcf6;
}

.preview-head {
  display: flex;
  align-items: flex-start;
  gap: 9px;
}

.preview-icon {
  display: grid;
  width: 24px;
  height: 24px;
  flex: 0 0 auto;
  place-items: center;
  border-radius: 999px;
  background: #e3f1dd;
  color: #4b7f3d;
}

.preview-head strong {
  color: #365c2d;
  font-size: 12.5px;
}

.preview-head p {
  margin: 2px 0 0;
  color: #698060;
  font-size: 10.5px;
}

.preview-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 7px;
}

.preview-grid > div {
  display: grid;
  gap: 1px;
  border: 1px solid #dcebd6;
  border-radius: 8px;
  padding: 7px 8px;
  background: #fff;
}

.preview-grid strong {
  color: #365c2d;
  font-size: 18px;
  line-height: 1;
}

.preview-grid span {
  color: #75856d;
  font-size: 9.5px;
  line-height: 1.3;
}

.preview > :last-child {
  justify-self: start;
}

@media (max-width: 560px) {
  .preview-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .validate-button,
  .preview-apply {
    width: 100%;
  }
}
</style>
