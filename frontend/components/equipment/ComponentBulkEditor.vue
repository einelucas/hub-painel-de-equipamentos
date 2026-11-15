<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { onBeforeRouteLeave } from "vue-router";
import { mdiChevronLeft, mdiChevronRight, mdiPencilOutline } from "@mdi/js";
import {
  VAlert,
  VBtn,
  VCheckbox,
  VChip,
  VIcon,
  VSelect,
  VTextField,
} from "vuetify/components";
import { useConfirm } from "~/composables/useConfirm";
import type { EquipmentComponent } from "~/types/equipment";

type Field = "tag" | "sector" | "startupAt" | "leadTimeDays" |
  "preStartDays" | "freightDays";
type Operation = "SET" | "CLEAR" | "FILL_EMPTY";
interface Change { field: Field; operation: Operation; value: string | number | null }
interface Draft { expectedUpdatedAt: string; changes: Partial<Record<Field, Change>> }
interface Preview {
  previewToken: string; requestedCount: number; changedCount: number; skippedCount: number;
  diffs: { componentId: string; field: string; previousValue: unknown;
    proposedValue: unknown; skippedReason: string | null }[]; errors: string[];
}

const props = defineProps<{ equipmentId: string; components: EquipmentComponent[] }>();
const emit = defineEmits<{ saved: []; exit: [] }>();
const api = useApi();
const { confirm } = useConfirm();
const selected = ref<string[]>([]);
const drafts = ref<Record<string, Draft>>({});
const preview = ref<Preview | null>(null);
const previewRequest = ref<Record<string, unknown> | null>(null);
const state = ref<"idle" | "validating" | "saving">("idle");
const error = ref("");
const success = ref("");
const tableScroll = ref<HTMLElement | null>(null);
const massField = ref<Field>("sector");
const massOp = ref<Operation>("SET");
const massValue = ref("");
const columns: { key: Field; label: string; kind: "text" | "date" | "number" }[] = [
  { key: "tag", label: "TAG", kind: "text" },
  { key: "sector", label: "Setor", kind: "text" },
  { key: "startupAt", label: "Startup", kind: "date" },
  { key: "leadTimeDays", label: "Lead time", kind: "number" },
  { key: "preStartDays", label: "Pré-start", kind: "number" },
  { key: "freightDays", label: "Frete", kind: "number" },
];
const recordLabels = computed(() => Object.fromEntries(
  props.components.map((component) => [component.id, component.name]),
));
const fieldLabels: Record<string, string> = {
  tag: "TAG",
  sector: "Setor",
  startup_at: "Startup",
  lead_time_days: "Lead time",
  pre_start_days: "Pré-start",
  freight_days: "Frete",
};
const massFields = columns.filter((column) => column.key !== "tag");
const massKind = computed(() => massFields.find((item) => item.key === massField.value)?.kind ?? "text");
const massOperationOptions = [
  { value: "SET", title: "Substituir" },
  { value: "FILL_EMPTY", title: "Preencher vazios" },
  { value: "CLEAR", title: "Limpar" },
];
const pendingCount = computed(() =>
  Object.values(drafts.value).reduce((sum, row) => sum + Object.keys(row.changes).length, 0),
);
const busy = computed(() => state.value !== "idle");

function baseValue(component: EquipmentComponent, field: Field): string {
  const raw = component[field];
  return raw === null || raw === undefined ? "" : String(raw);
}
function currentValue(component: EquipmentComponent, field: Field): string {
  const change = drafts.value[component.id]?.changes[field];
  if (!change) return baseValue(component, field);
  return change.operation === "CLEAR" ? "" : String(change.value ?? "");
}
function setChange(component: EquipmentComponent, field: Field, operation: Operation,
  value: string | number | null): void {
  const data = drafts.value[component.id] ?? {
    expectedUpdatedAt: component.updatedAt, changes: {},
  };
  data.changes[field] = { field, operation, value };
  drafts.value = { ...drafts.value, [component.id]: { ...data, changes: { ...data.changes } } };
  preview.value = null;
  error.value = "";
  success.value = "";
}
function setCell(
  component: EquipmentComponent,
  column: typeof columns[number],
  next: unknown,
): void {
  const raw = next === null || next === undefined ? "" : String(next);
  if (raw === baseValue(component, column.key)) {
    const data = drafts.value[component.id];
    if (data) {
      const changes = Object.fromEntries(
        Object.entries(data.changes).filter(([key]) => key !== column.key),
      ) as Draft["changes"];
      drafts.value = Object.keys(changes).length
        ? { ...drafts.value, [component.id]: { ...data, changes } }
        : Object.fromEntries(Object.entries(drafts.value).filter(([key]) => key !== component.id));
    }
    return;
  }
  if (column.kind === "number" && raw !== "" && (!/^\d+$/.test(raw))) {
    error.value = "Dias precisam ser inteiros não negativos.";
    return;
  }
  const value = raw === "" ? null : column.kind === "number" ? Number(raw) : raw;
  setChange(component, column.key, value === null ? "CLEAR" : "SET", value);
}
function toggle(id: string, checked: boolean): void {
  selected.value = checked
    ? [...new Set([...selected.value, id])]
    : selected.value.filter((item) => item !== id);
}
function massFieldChanged(value: unknown): void {
  massField.value = String(value) as Field;
  massValue.value = "";
}
function scrollColumns(direction: -1 | 1): void {
  tableScroll.value?.scrollBy({ left: direction * 440, behavior: "smooth" });
}
function applyMass(): void {
  const value = massOp.value === "CLEAR" ? null :
    massKind.value === "number" ? Number(massValue.value) : massValue.value;
  if (massOp.value !== "CLEAR" && !massValue.value) {
    error.value = "Informe o valor coletivo.";
    return;
  }
  if (massKind.value === "number" && massOp.value !== "CLEAR" &&
    (!/^\d+$/.test(massValue.value))) {
    error.value = "Dias precisam ser inteiros não negativos.";
    return;
  }
  for (const component of props.components.filter((row) => selected.value.includes(row.id))) {
    setChange(component, massField.value, massOp.value, value);
  }
  success.value = `Alteração adicionada ao rascunho de ${selected.value.length} componente(s).`;
}
function requestBody(): Record<string, unknown> {
  return {
    items: Object.entries(drafts.value).map(([componentId, value]) => ({
      componentId, expectedUpdatedAt: value.expectedUpdatedAt,
      changes: Object.values(value.changes),
    })),
  };
}
async function review(): Promise<void> {
  if (!pendingCount.value || busy.value) return;
  state.value = "validating";
  error.value = "";
  try {
    const body = requestBody();
    preview.value = await api.post<Preview>(
      `/equipments/${props.equipmentId}/components/bulk/preview`, body,
    );
    previewRequest.value = body;
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "Não foi possível validar componentes.";
  } finally { state.value = "idle"; }
}
async function save(): Promise<void> {
  if (!preview.value || !previewRequest.value || busy.value) return;
  state.value = "saving";
  error.value = "";
  try {
    const result = await api.post<{ updatedCount: number }>(
      `/equipments/${props.equipmentId}/components/bulk/apply`,
      { ...previewRequest.value, previewToken: preview.value.previewToken,
        idempotencyKey: window.crypto.randomUUID() },
    );
    success.value = `${result.updatedCount} componente(s) atualizado(s).`;
    drafts.value = {};
    selected.value = [];
    preview.value = null;
    previewRequest.value = null;
    emit("saved");
  } catch (caught) {
    preview.value = null;
    error.value = caught instanceof Error ? caught.message : "Falha ao salvar. Revise novamente.";
  } finally { state.value = "idle"; }
}
async function confirmDiscard(): Promise<boolean> {
  if (!pendingCount.value) return true;
  return confirm({
    title: "Descartar alterações?",
    message: "Descartar todas as alterações dos componentes?",
    detail: `${pendingCount.value} alteração(ões) pendente(s) serão perdidas.`,
    confirmLabel: "Descartar",
    cancelLabel: "Continuar editando",
    tone: "danger",
    icon: "warning",
  });
}
async function discard(): Promise<void> {
  if (!await confirmDiscard()) return;
  drafts.value = {};
  selected.value = [];
  emit("exit");
}
function beforeUnload(event: BeforeUnloadEvent): void {
  if (pendingCount.value) event.preventDefault();
}
onMounted(() => window.addEventListener("beforeunload", beforeUnload));
onBeforeUnmount(() => window.removeEventListener("beforeunload", beforeUnload));
onBeforeRouteLeave(() => confirmDiscard());
defineExpose({ hasPending: () => pendingCount.value > 0, confirmDiscard });
</script>

<template>
  <div class="component-bulk" :aria-busy="busy" data-testid="component-bulk-editor">
    <div class="edit-mode-header">
      <div class="edit-mode-title">
        <span class="edit-mode-icon" aria-hidden="true"><VIcon :icon="mdiPencilOutline" size="18" /></span>
        <div>
          <div class="edit-mode-eyebrow">Edição de componentes</div>
          <strong>Edite os campos e revise antes de salvar</strong>
          <p>Selecione componentes para aplicar a mesma alteração em várias linhas.</p>
        </div>
      </div>
      <div class="edit-status" role="status" aria-live="polite">
        <VChip size="small" variant="tonal" color="primary">
          {{ selected.length }} linha(s) selecionada(s)
        </VChip>
        <VChip size="small" variant="outlined" :color="pendingCount ? 'warning' : 'default'">
          {{ pendingCount }} alteração(ões)
        </VChip>
      </div>
    </div>
    <div class="toolbar" aria-label="Ações de seleção e navegação">
      <div class="selection-actions">
        <VBtn
          variant="tonal"
          size="small"
          :disabled="busy"
          @click="selected = components.map((row) => row.id)"
        >Selecionar todos</VBtn>
        <VBtn
          variant="text"
          size="small"
          :disabled="busy || !selected.length"
          @click="selected = []"
        >Limpar seleção</VBtn>
      </div>
      <span class="spacer" />
      <div class="column-navigation">
        <span>Explorar colunas</span>
        <VBtn :icon="mdiChevronLeft" size="x-small" variant="text" title="Ver colunas anteriores" aria-label="Ver colunas anteriores" @click="scrollColumns(-1)" />
        <VBtn :icon="mdiChevronRight" size="x-small" variant="text" title="Ver próximas colunas" aria-label="Ver próximas colunas" @click="scrollColumns(1)" />
      </div>
    </div>
    <div v-if="selected.length" class="mass-panel">
      <div class="mass-panel-heading">
        <strong>Alteração coletiva</strong>
        <span>Aplicar em {{ selected.length }} componente(s)</span>
      </div>
      <div class="mass-control">
        <VSelect
          :model-value="massField"
          :items="massFields"
          item-title="label"
          item-value="key"
          label="Campo"
          density="compact"
          hide-details
          :disabled="busy"
          @update:model-value="massFieldChanged"
        />
      </div>
      <div class="mass-control">
        <VSelect
          v-model="massOp"
          :items="massOperationOptions"
          label="Operação"
          density="compact"
          hide-details
          :disabled="busy"
        />
      </div>
      <div v-if="massOp !== 'CLEAR'" class="mass-control mass-value">
        <VTextField
          v-model="massValue"
          :type="massKind === 'date' ? 'date' :
          massKind === 'number' ? 'number' : 'text'" :min="massKind === 'number' ? 0 : undefined"
          label="Valor"
          density="compact"
          hide-details
          :disabled="busy"
        />
      </div>
      <VBtn
        class="apply-mass-button"
        variant="flat"
        color="primary"
        size="small"
        :disabled="busy"
        @click="applyMass"
      >Aplicar ao rascunho</VBtn>
    </div>
    <VAlert v-if="error" type="error" density="compact" variant="tonal" role="alert">
      {{ error }}
    </VAlert>
    <VAlert v-if="success" type="success" density="compact" variant="tonal">
      {{ success }}
    </VAlert>
    <div ref="tableScroll" class="table-scroll">
      <table class="edit-table">
        <thead><tr>
          <th class="select-column"><span class="sr-only">Selecionar</span></th>
          <th class="component-column">Componente <span class="readonly-label">Somente leitura</span></th>
          <th v-for="column in columns" :key="column.key">{{ column.label }}</th>
        </tr></thead>
        <tbody>
          <tr v-for="component in components" :key="component.id">
            <td class="select-column"><VCheckbox
              class="row-checkbox"
              :model-value="selected.includes(component.id)"
              :disabled="busy"
              color="primary"
              density="compact"
              hide-details
              :aria-label="`Selecionar ${component.name}`"
              @update:model-value="toggle(component.id, Boolean($event))"
            /></td>
            <td class="name component-column">{{ component.name }}</td>
            <td
              v-for="column in columns"
              :key="column.key"
              :class="{ changed: Boolean(drafts[component.id]?.changes[column.key]) }"
            >
              <VTextField
                class="cell-control"
                :type="column.kind"
                :model-value="currentValue(component, column.key)"
                :min="column.kind === 'number' ? 0 : undefined"
                :label="column.label"
                density="compact"
                hide-details
                :aria-label="`${column.label}: ${component.name}`"
                :disabled="busy"
                @update:model-value="setCell(component, column, $event)"
              />
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <div class="footer">
      <span>{{ state === "validating" ? "Validando…" :
        state === "saving" ? "Gravando lote…" : "Altere células ou selecione componentes" }}</span>
      <div class="footer-actions">
        <VBtn variant="text" :disabled="busy" @click="discard">Sair da edição</VBtn>
        <VBtn
          variant="flat"
          color="primary"
          :loading="state === 'validating'"
          :disabled="!pendingCount || busy"
          @click="review"
        >Revisar alterações</VBtn>
      </div>
    </div>
    <BulkEditReviewDialog
      :preview="preview"
      :saving="state === 'saving'"
      :record-labels="recordLabels"
      :field-labels="fieldLabels"
      @close="preview = null"
      @confirm="save"
    />
  </div>
</template>

<style scoped>
.component-bulk { display: grid; gap: 12px; padding: 0 16px 18px; background: #f8fafc; border-top: 1px solid #dbe5f0; }
.edit-mode-header { display: flex; align-items: center; justify-content: space-between; gap: 20px; margin: 0 -16px; padding: 16px 18px; background: #f3f7fc; border-bottom: 1px solid #d9e6f5; }
.edit-mode-title { display: flex; align-items: flex-start; gap: 12px; min-width: 0; }
.edit-mode-title strong { display: block; color: #173456; font-size: 14px; }
.edit-mode-title p { margin: 3px 0 0; color: #64748b; font-size: 12px; }
.edit-mode-eyebrow { margin-bottom: 2px; color: #2867ad; font-size: 10px; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }
.edit-mode-icon { display: grid; flex: 0 0 34px; width: 34px; height: 34px; place-items: center; border-radius: 10px; background: #fff; color: #2867ad; box-shadow: 0 3px 10px rgb(33 82 135 / 12%); }
.edit-status, .toolbar, .selection-actions, .column-navigation, .mass-panel, .footer, .footer-actions { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.edit-status { justify-content: flex-end; }
.toolbar { min-height: 38px; }
.spacer { flex: 1; }
.column-navigation { color: #64748b; font-size: 11px; }
.mass-panel { gap: 12px; padding: 14px; border: 1px solid #dce6f0; border-radius: 12px; background: #fff; box-shadow: 0 4px 16px rgb(31 55 85 / 6%); }
.mass-panel-heading { display: grid; align-self: center; min-width: 145px; }
.mass-panel-heading strong { color: #213758; font-size: 13px; }
.mass-panel-heading span { color: #718096; font-size: 11px; }
.mass-control { width: 185px; }
.mass-value { min-width: 210px; flex: 1; }
.apply-mass-button { margin-bottom: 1px; }
.table-scroll { overflow: auto; max-width: 100%; max-height: min(62vh, 680px); border: 1px solid #dce4ee; border-radius: 12px; background: #fff; box-shadow: 0 5px 20px rgb(31 55 85 / 5%); scrollbar-color: #94a3b8 #e9eef5; }
.edit-table { border-collapse: separate; border-spacing: 0; min-width: 1260px; width: 100%; text-align: left; font-size: 12px; }
.edit-table th, .edit-table td { height: 58px; padding: 9px 10px; border-bottom: 1px solid #e5ebf2; background: #fff; vertical-align: middle; }
.edit-table th { position: sticky; top: 0; z-index: 3; height: 46px; white-space: nowrap; background: #f3f6fa; color: #41546c; font-size: 11px; font-weight: 750; }
.edit-table tbody tr:hover td { background: #f8fbff; }
.edit-table .select-column { position: sticky; left: 0; z-index: 2; width: 46px; min-width: 46px; text-align: center; }
.edit-table .component-column { position: sticky; left: 46px; z-index: 2; min-width: 210px; max-width: 250px; box-shadow: 8px 0 12px -12px rgb(31 55 85 / 55%); }
.edit-table th.select-column, .edit-table th.component-column { z-index: 5; background: #edf2f7; }
.edit-table .name { color: #213758; font-weight: 650; line-height: 1.35; }
.edit-table td.changed { background: #edf6ff; box-shadow: inset 0 0 0 1px #b9d7f7; }
.edit-table tbody tr:hover td.changed { background: #e8f3ff; }
.readonly-label { display: block; margin-top: 2px; color: #8795a8; font-size: 9px; font-weight: 600; text-transform: uppercase; }
.cell-control { width: 165px; min-width: 165px; max-width: 165px; }
.cell-control :deep(.v-field), .mass-control :deep(.v-field) { background: rgb(var(--v-theme-surface)); }
.row-checkbox { display: inline-flex; vertical-align: middle; }
.row-checkbox :deep(.v-selection-control) { justify-content: center; }
.footer { position: sticky; bottom: 0; z-index: 7; justify-content: space-between; margin: 0 -16px -18px; padding: 12px 18px; border-top: 1px solid #dce4ee; background: rgb(255 255 255 / 96%); box-shadow: 0 -8px 22px rgb(31 55 85 / 7%); backdrop-filter: blur(8px); }
.footer span { color: #64748b; font-size: 12px; }
@media (max-width: 760px) {
  .component-bulk { padding: 8px; }
  .edit-mode-header { align-items: flex-start; flex-direction: column; margin: -8px -8px 0; }
  .edit-status { justify-content: flex-start; }
  .mass-control { width: 100%; }
  .footer { margin: 0 -8px -8px; }
}
</style>
