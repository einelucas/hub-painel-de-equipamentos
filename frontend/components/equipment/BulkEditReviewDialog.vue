<script setup lang="ts">
import { VBtn, VCard, VCardActions, VCardText, VCardTitle, VDialog, VSpacer } from "vuetify/components";

interface BulkEditDiff {
  equipmentId?: string;
  componentId?: string;
  field: string;
  previousValue: unknown;
  proposedValue: unknown;
  skippedReason: string | null;
}

interface BulkEditPreview {
  previewToken: string;
  requestedCount: number;
  changedCount: number;
  skippedCount: number;
  diffs: BulkEditDiff[];
  errors: string[];
}

defineProps<{ preview: BulkEditPreview | null; saving: boolean }>();
const emit = defineEmits<{ confirm: []; close: [] }>();

function label(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (Array.isArray(value)) return value.length ? value.join(", ") : "Nenhum";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}
</script>

<template>
  <VDialog :model-value="Boolean(preview)" max-width="900" scrollable persistent>
    <VCard v-if="preview" data-testid="bulk-edit-review">
      <VCardTitle>Revisar alterações</VCardTitle>
      <VCardText>
        <p class="summary">
          {{ preview.changedCount }} registro(s) alterados · {{ preview.skippedCount }}
          campo(s) ignorados ou sem diferença. Nenhum dado foi gravado ainda.
        </p>
        <div v-if="preview.errors?.length" role="alert" class="error-list">
          <p v-for="(error, i) in preview.errors" :key="i">{{ error }}</p>
        </div>
        <div class="review-scroller">
          <table class="review-table">
            <thead>
              <tr><th>Registro</th><th>Campo</th><th>Anterior</th><th>Novo</th><th>Resultado</th></tr>
            </thead>
            <tbody>
              <tr v-for="(diff, index) in preview.diffs" :key="index">
                <td>{{ diff.equipmentId ?? diff.componentId }}</td>
                <td>{{ diff.field }}</td>
                <td>{{ label(diff.previousValue) }}</td>
                <td>{{ label(diff.proposedValue) }}</td>
                <td>{{ diff.skippedReason === "ALREADY_FILLED" ? "Preservado (já preenchido)" : diff.skippedReason === "UNCHANGED" ? "Sem alteração" : "Alterar" }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </VCardText>
      <VCardActions class="actions">
        <VSpacer />
        <VBtn variant="text" :disabled="saving" @click="emit('close')">Voltar ao rascunho</VBtn>
        <VBtn
          color="primary"
          variant="flat"
          :loading="saving"
          :disabled="preview.changedCount === 0 || preview.errors?.length > 0"
          @click="emit('confirm')"
        >
          Confirmar e salvar
        </VBtn>
      </VCardActions>
    </VCard>
  </VDialog>
</template>

<style scoped>
.summary { margin: 0 0 16px; color: #475569; font-size: 14px; }
.review-scroller { overflow-x: auto; max-height: 55vh; }
.review-table { width: 100%; border-collapse: collapse; font-size: 12px; text-align: left; }
.review-table td, .review-table th { padding: 10px 12px; border-bottom: 1px solid #e2e8f0; }
.review-table td { word-break: break-word; }
.review-table th { background: #f1f5f9; color: #334155; position: sticky; top: 0; }
.actions { padding: 12px 18px; }
.error-list { color: #991b1b; padding: 8px; }
</style>
