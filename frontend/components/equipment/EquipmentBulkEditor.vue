<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
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
import SearchableMultiSelect from "~/components/ui/SearchableMultiSelect.vue";
import SearchableSelect from "~/components/ui/SearchableSelect.vue";
import { useConfirm } from "~/composables/useConfirm";
import type { Equipment } from "~/types/equipment";

type Field = "disciplineId" | "responsibleUserId" | "eapNodeId" | "origin" |
  "startupAt" | "criticalityLabelId" | "workPackageIds";
type Operation = "SET" | "CLEAR" | "FILL_EMPTY" | "ADD" | "REMOVE" | "REPLACE";
interface Option { id: string; label: string }
interface CellChange { field: Field; operation: Operation; value?: string | string[] | null }
interface RowDraft { expectedUpdatedAt: string; changes: Partial<Record<Field, CellChange>> }
interface SelectionItem { equipmentId: string; name: string; expectedUpdatedAt: string }
interface Preview {
  previewToken: string; requestedCount: number; changedCount: number; skippedCount: number;
  diffs: { equipmentId: string; field: string; previousValue: unknown;
    proposedValue: unknown; skippedReason: string | null }[]; errors: string[];
}
const props = defineProps<{
  equipments: Equipment[];
  projectContextId: string;
  filters: Record<string, unknown>;
  total: number;
  disciplineOptions: Option[];
  responsibleOptions: Option[];
  eapOptions: Option[];
  criticalityOptions: Option[];
  workPackageOptions: Option[];
}>();
const emit = defineEmits<{ saved: []; exit: [] }>();
const api = useApi();
const { confirm } = useConfirm();
const selected = ref<string[]>([]);
const versions = ref<Record<string, string>>({});
const recordLabels = ref<Record<string, string>>({});
const drafts = ref<Record<string, RowDraft>>({});
const preview = ref<Preview | null>(null);
const previewRequest = ref<Record<string, unknown> | null>(null);
const state = ref<"idle" | "selecting" | "validating" | "saving">("idle");
const error = ref("");
const success = ref("");
const gridScroll = ref<HTMLElement | null>(null);
const massField = ref<Field>("disciplineId");
const massOp = ref<Operation>("SET");
const massValue = ref("");
const massWpIds = ref<string[]>([]);
const editing = computed(() => Object.keys(drafts.value).length > 0);
const pendingCount = computed(() =>
  Object.values(drafts.value).reduce((total, item) => total + Object.keys(item.changes).length, 0),
);
const busy = computed(() => state.value !== "idle");
const fields: { key: Field; label: string; kind: "select" | "text" | "date" | "wps" }[] = [
  { key: "disciplineId", label: "Disciplina", kind: "select" },
  { key: "responsibleUserId", label: "Responsável", kind: "select" },
  { key: "eapNodeId", label: "Área / EAP", kind: "select" },
  { key: "origin", label: "Origem", kind: "text" },
  { key: "startupAt", label: "Startup", kind: "date" },
  { key: "criticalityLabelId", label: "Criticidade", kind: "select" },
  { key: "workPackageIds", label: "Work Packages", kind: "wps" },
];
const fieldLabels: Record<string, string> = {
  discipline_id: "Disciplina",
  responsible_user_id: "Responsável",
  eap_node_id: "Área / EAP",
  origin: "Origem",
  startup_at: "Startup",
  criticality_label_id: "Criticidade",
  work_package_ids: "Work Packages",
};
const massOperationOptions = computed(() => massField.value === "workPackageIds"
  ? [
      { value: "ADD", title: "Adicionar" },
      { value: "REMOVE", title: "Remover" },
      { value: "REPLACE", title: "Substituir" },
      { value: "CLEAR", title: "Limpar" },
    ]
  : [
      { value: "SET", title: "Substituir" },
      { value: "FILL_EMPTY", title: "Preencher vazios" },
      { value: "CLEAR", title: "Limpar" },
    ]);
const valueLabels = computed(() => ({
  discipline_id: Object.fromEntries(props.disciplineOptions.map((item) => [item.id, item.label])),
  responsible_user_id: Object.fromEntries(props.responsibleOptions.map((item) => [item.id, item.label])),
  eap_node_id: Object.fromEntries(props.eapOptions.map((item) => [item.id, item.label])),
  criticality_label_id: Object.fromEntries(props.criticalityOptions.map((item) => [item.id, item.label])),
  work_package_ids: Object.fromEntries(props.workPackageOptions.map((item) => [item.id, item.label])),
}));

watch(() => props.equipments, (items) => {
  for (const item of items) {
    if (!versions.value[item.id]) versions.value[item.id] = item.updatedAt;
    recordLabels.value[item.id] = item.name;
  }
}, { immediate: true });

function options(field: Field): Option[] {
  if (field === "disciplineId") return props.disciplineOptions;
  if (field === "responsibleUserId") return props.responsibleOptions;
  if (field === "eapNodeId") return props.eapOptions;
  if (field === "criticalityLabelId") return props.criticalityOptions;
  if (field === "workPackageIds") return props.workPackageOptions;
  return [];
}
function baseValue(row: Equipment, field: Field): string | string[] {
  switch (field) {
    case "disciplineId": return row.discipline?.id ?? "";
    case "responsibleUserId": return row.responsibleUser?.id ?? "";
    case "eapNodeId": return row.eapNode?.id ?? "";
    case "origin": return row.origin ?? "";
    case "startupAt": return row.startupAt ?? "";
    case "criticalityLabelId": return row.criticalityLabel?.id ?? "";
    case "workPackageIds": return row.workPackages.map((wp) => wp.id);
  }
}
function draftValue(row: Equipment, field: Field): string | string[] {
  const change = drafts.value[row.id]?.changes[field];
  if (!change) return baseValue(row, field);
  if (change.operation === "CLEAR") return field === "workPackageIds" ? [] : "";
  if (field === "workPackageIds") {
    const start = baseValue(row, field) as string[];
    const values = change.value as string[];
    if (change.operation === "ADD") return [...new Set([...start, ...values])];
    if (change.operation === "REMOVE") return start.filter((id) => !values.includes(id));
    return values;
  }
  return String(change.value ?? "");
}
function setChange(
  id: string, field: Field, operation: Operation, value: string | string[] | null,
  version?: string,
): void {
  const current = drafts.value[id] ?? {
    expectedUpdatedAt: version ?? versions.value[id] ?? "",
    changes: {},
  };
  if (!current.expectedUpdatedAt) {
    error.value = "Versão ausente. Atualize a seleção antes de editar.";
    return;
  }
  current.changes[field] = { field, operation, value };
  drafts.value = { ...drafts.value, [id]: { ...current, changes: { ...current.changes } } };
  preview.value = null;
  error.value = "";
  success.value = "";
}
function cellChanged(row: Equipment, field: Field, next: unknown): void {
  const value = next === null || next === undefined ? "" : String(next);
  if (value === baseValue(row, field)) {
    const current = drafts.value[row.id];
    if (current) {
      const changes = Object.fromEntries(
        Object.entries(current.changes).filter(([key]) => key !== field),
      ) as RowDraft["changes"];
      drafts.value = Object.keys(changes).length
        ? { ...drafts.value, [row.id]: { ...current, changes } }
        : Object.fromEntries(Object.entries(drafts.value).filter(([key]) => key !== row.id));
    }
    return;
  }
  setChange(row.id, field, value ? "SET" : "CLEAR", value || null, row.updatedAt);
}
function wpChanged(row: Equipment, chosen: string[]): void {
  setChange(row.id, "workPackageIds", "REPLACE", chosen, row.updatedAt);
}
function toggle(row: Equipment, checked: boolean): void {
  versions.value[row.id] = versions.value[row.id] ?? row.updatedAt;
  selected.value = checked
    ? [...new Set([...selected.value, row.id])]
    : selected.value.filter((id) => id !== row.id);
}
function selectPage(): void {
  const ids = props.equipments.map((row) => row.id);
  selected.value = [...new Set([...selected.value, ...ids])];
}
async function selectAllFiltered(): Promise<void> {
  if (busy.value) return;
  if (editing.value && !await confirm({
    title: "Substituir seleção?",
    message: "Selecionar todos os resultados filtrados?",
    detail: "O rascunho atual será mantido, mas a seleção de linhas será substituída.",
    confirmLabel: "Continuar",
    cancelLabel: "Voltar",
    tone: "primary",
    icon: "warning",
  })) {
    return;
  }
  state.value = "selecting";
  error.value = "";
  try {
    const result = await api.get<{ total: number; items: SelectionItem[] }>(
      "/equipments/bulk/selection",
      { ...props.filters, projectContextId: props.projectContextId },
      { force: true },
    );
    for (const item of result.items) {
      if (!versions.value[item.equipmentId]) {
        versions.value[item.equipmentId] = item.expectedUpdatedAt;
      }
      recordLabels.value[item.equipmentId] = item.name;
    }
    selected.value = result.items.map((item) => item.equipmentId);
    success.value = `Selecionados ${result.total} equipamentos em todas as páginas filtradas.`;
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "Falha ao selecionar.";
  } finally { state.value = "idle"; }
}
function massChanged(value: unknown): void {
  massField.value = String(value) as Field;
  massValue.value = "";
  massWpIds.value = [];
  massOp.value = massField.value === "workPackageIds" ? "ADD" : "SET";
}
function scrollTable(direction: -1 | 1): void {
  gridScroll.value?.scrollBy({ left: direction * 520, behavior: "smooth" });
}
function applyMass(): void {
  if (!selected.value.length) return;
  const isWp = massField.value === "workPackageIds";
  const value = massOp.value === "CLEAR" ? null : isWp ? massWpIds.value : massValue.value;
  if (value !== null && (Array.isArray(value) ? !value.length : !value.trim())) {
    error.value = "Informe o valor da alteração coletiva.";
    return;
  }
  for (const id of selected.value) {
    setChange(id, massField.value, massOp.value, value, versions.value[id]);
  }
  success.value = `Alteração aplicada ao rascunho de ${selected.value.length} linha(s).`;
}
function requestBody(): Record<string, unknown> {
  return {
    projectContextId: props.projectContextId,
    items: Object.entries(drafts.value).map(([equipmentId, data]) => ({
      equipmentId, expectedUpdatedAt: data.expectedUpdatedAt,
      changes: Object.values(data.changes),
    })),
  };
}
async function review(): Promise<void> {
  if (!editing.value || busy.value) return;
  state.value = "validating";
  error.value = "";
  try {
    const body = requestBody();
    preview.value = await api.post<Preview>("/equipments/bulk/preview", body);
    previewRequest.value = body;
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "Não foi possível validar o lote.";
  } finally { state.value = "idle"; }
}
async function save(): Promise<void> {
  if (!preview.value || !previewRequest.value || busy.value) return;
  state.value = "saving";
  error.value = "";
  try {
    const result = await api.post<{ updatedCount: number }>(
      "/equipments/bulk/apply",
      { ...previewRequest.value, previewToken: preview.value.previewToken,
        idempotencyKey: window.crypto.randomUUID() },
    );
    success.value = `${result.updatedCount} equipamento(s) atualizado(s).`;
    drafts.value = {};
    selected.value = [];
    versions.value = {};
    preview.value = null;
    previewRequest.value = null;
    emit("saved");
  } catch (caught) {
    preview.value = null;
    error.value = caught instanceof Error ? caught.message : "Falha na gravação. Revise novamente.";
  } finally { state.value = "idle"; }
}
async function confirmDiscard(): Promise<boolean> {
  if (!editing.value) return true;
  return confirm({
    title: "Descartar alterações?",
    message: "Descartar todas as alterações não salvas?",
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
  if (!editing.value) return;
  event.preventDefault();
}
onMounted(() => window.addEventListener("beforeunload", beforeUnload));
onBeforeUnmount(() => window.removeEventListener("beforeunload", beforeUnload));
onBeforeRouteLeave(() => confirmDiscard());
defineExpose({ hasPending: () => editing.value, confirmDiscard });
</script>

<template>
  <div class="bulk-editor" data-testid="equipment-bulk-editor" :aria-busy="busy">
    <div class="edit-mode-header">
      <div class="edit-mode-title">
        <span class="edit-mode-icon" aria-hidden="true"><VIcon :icon="mdiPencilOutline" size="18" /></span>
        <div>
          <div class="edit-mode-eyebrow">Edição em tabela</div>
          <strong>Edite os campos e revise antes de salvar</strong>
          <p>Selecione linhas para aplicar uma mesma alteração a vários equipamentos.</p>
        </div>
      </div>
      <div class="edit-status" role="status" aria-live="polite">
        <VChip size="small" variant="tonal" color="primary">{{ selected.length }} linha(s) selecionada(s)</VChip>
        <VChip size="small" variant="outlined" :color="pendingCount ? 'warning' : 'default'">
          {{ pendingCount }} alteração(ões)
        </VChip>
      </div>
    </div>
    <div class="bulk-actions" aria-label="Ações de seleção e navegação">
      <div class="selection-actions">
        <VBtn size="small" variant="tonal" :disabled="busy" @click="selectPage">Selecionar página</VBtn>
        <VBtn
          size="small"
          variant="tonal"
          :loading="state === 'selecting'"
          :disabled="busy"
          @click="selectAllFiltered"
        >Todos os filtrados ({{ total }})</VBtn>
        <VBtn size="small" variant="text" :disabled="busy || !selected.length" @click="selected = []">Limpar seleção</VBtn>
      </div>
      <span class="spacer" />
      <div class="column-navigation">
        <span>Explorar colunas</span>
        <VBtn :icon="mdiChevronLeft" size="x-small" variant="text" title="Ver colunas anteriores" aria-label="Ver colunas anteriores" @click="scrollTable(-1)" />
        <VBtn :icon="mdiChevronRight" size="x-small" variant="text" title="Ver próximas colunas" aria-label="Ver próximas colunas" @click="scrollTable(1)" />
      </div>
    </div>
    <div v-if="selected.length" class="mass-panel" data-testid="mass-edit-panel">
      <div class="mass-panel-heading">
        <strong>Alteração coletiva</strong>
        <span>Aplicar em {{ selected.length }} equipamento(s)</span>
      </div>
      <div class="mass-control">
        <VSelect
          :model-value="massField"
          :items="fields"
          item-title="label"
          item-value="key"
          label="Campo"
          density="compact"
          hide-details
          :disabled="busy"
          data-testid="mass-field-select"
          @update:model-value="massChanged"
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
          data-testid="mass-operation-select"
        />
      </div>
      <div v-if="massOp !== 'CLEAR'" class="mass-control mass-value">
        <SearchableMultiSelect
          v-if="massField === 'workPackageIds'"
          v-model="massWpIds"
          class="mass-wp-select"
          :options="workPackageOptions"
          label="Work Packages"
          placeholder="Buscar e selecionar vários"
          :disabled="busy"
          test-id="mass-work-packages"
        />
        <SearchableSelect
          v-else-if="['disciplineId','responsibleUserId','eapNodeId','criticalityLabelId'].includes(massField)"
          v-model="massValue"
          :options="options(massField)"
          label="Novo valor"
          placeholder="Digite para buscar"
          empty-label="Escolher"
          :disabled="busy"
        />
        <VTextField
          v-else
          v-model="massValue"
          :type="massField === 'startupAt' ? 'date' : 'text'"
          label="Novo valor"
          density="compact"
          hide-details
          :disabled="busy"
        />
      </div>
      <VBtn class="apply-mass-button" color="primary" size="small" variant="flat" :disabled="busy" @click="applyMass">
        Aplicar ao rascunho
      </VBtn>
    </div>
    <VAlert v-if="error" type="error" variant="tonal" density="compact" role="alert">{{ error }}</VAlert>
    <VAlert v-if="success" type="success" variant="tonal" density="compact">{{ success }}</VAlert>
    <div ref="gridScroll" class="grid-scroll">
      <table class="edit-table">
        <thead><tr>
          <th class="select-column"><span class="sr-only">Selecionar</span></th>
          <th class="equipment-column">Equipamento <span class="readonly-label">Somente leitura</span></th>
          <th v-for="field in fields" :key="field.key">{{ field.label }}</th>
          <th>Etapa (somente leitura)</th>
        </tr></thead>
        <tbody>
          <tr v-for="row in equipments" :key="row.id">
            <td class="select-column"><VCheckbox
              class="row-checkbox"
              :model-value="selected.includes(row.id)"
              :disabled="busy"
              color="primary"
              density="compact"
              hide-details
              :aria-label="`Selecionar ${row.name}`"
              @update:model-value="toggle(row, Boolean($event))"
            /></td>
            <td class="name equipment-column"><NuxtLink :to="`/equipamentos/${row.id}`">{{ row.name }}</NuxtLink></td>
            <td
              v-for="field in fields"
              :key="field.key"
              :class="{ changed: Boolean(drafts[row.id]?.changes[field.key]) }"
            >
              <SearchableSelect
                v-if="field.kind === 'select'"
                class="cell-control cell-select"
                :model-value="draftValue(row, field.key) as string"
                :options="options(field.key)"
                :label="field.label"
                placeholder="Digite para buscar"
                empty-label="Não informado"
                :disabled="busy"
                :test-id="`${field.key}-${row.id}`"
                @update:model-value="cellChanged(row, field.key, $event)"
              />
              <SearchableMultiSelect
                v-else-if="field.kind === 'wps'"
                class="wp-multi-select"
                :model-value="draftValue(row, field.key) as string[]"
                :options="workPackageOptions"
                label="Work Packages"
                placeholder="Buscar e adicionar"
                :disabled="busy"
                :test-id="`work-packages-${row.id}`"
                @update:model-value="wpChanged(row, $event)"
              />
              <VTextField
                v-else
                class="cell-control"
                :model-value="draftValue(row, field.key)"
                :type="field.kind === 'date' ? 'date' : 'text'"
                :label="field.label"
                density="compact"
                hide-details
                :disabled="busy"
                :aria-label="`${field.label}: ${row.name}`"
                @update:model-value="cellChanged(row, field.key, $event)"
              />
            </td>
            <td>{{ row.stageName }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div class="bulk-footer">
      <span>{{ state === "selecting" ? "Selecionando…" :
        state === "validating" ? "Validando prévia…" :
        state === "saving" ? "Gravando lote…" : "Alterações não são salvas automaticamente" }}</span>
      <div class="footer-buttons">
        <VBtn variant="text" :disabled="busy" @click="discard">Sair da edição</VBtn>
        <VBtn
          color="primary"
          variant="flat"
          :loading="state === 'validating'"
          :disabled="!editing || busy"
          @click="review"
        >Revisar alterações</VBtn>
      </div>
    </div>
    <BulkEditReviewDialog
      :preview="preview"
      :saving="state === 'saving'"
      :record-labels="recordLabels"
      :field-labels="fieldLabels"
      :value-labels="valueLabels"
      @close="preview = null"
      @confirm="save"
    />
  </div>
</template>

<style scoped>
.bulk-editor { padding: 0 16px 18px; display: grid; gap: 12px; background: #f8fafc; border-top: 1px solid #dbe5f0; }
.edit-mode-header { display: flex; align-items: center; justify-content: space-between; gap: 20px; margin: 0 -16px; padding: 16px 18px; background: #f3f7fc; border-bottom: 1px solid #d9e6f5; }
.edit-mode-title { display: flex; align-items: flex-start; gap: 12px; min-width: 0; }
.edit-mode-title strong { display: block; color: #173456; font-size: 14px; }
.edit-mode-title p { margin: 3px 0 0; color: #64748b; font-size: 12px; }
.edit-mode-eyebrow { margin-bottom: 2px; color: #2867ad; font-size: 10px; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }
.edit-mode-icon { display: grid; flex: 0 0 34px; width: 34px; height: 34px; place-items: center; border-radius: 10px; background: #fff; color: #2867ad; box-shadow: 0 3px 10px rgb(33 82 135 / 12%); }
.edit-status { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 8px; }
.bulk-actions, .bulk-footer, .footer-buttons { display: flex; flex-wrap: wrap; align-items: center; gap: 9px; }
.bulk-actions { min-height: 38px; }
.selection-actions, .column-navigation { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }
.column-navigation { color: #64748b; font-size: 11px; }
.spacer { flex: 1; }
.muted, .bulk-footer span { font-size: 12px; color: #64748b; }
.mass-panel { display: flex; align-items: end; flex-wrap: wrap; gap: 12px; background: #fff;
  border: 1px solid #dce6f0; border-radius: 12px; padding: 14px; box-shadow: 0 4px 16px rgb(31 55 85 / 6%); }
.mass-panel-heading { display: grid; align-self: center; min-width: 145px; }
.mass-panel-heading strong { color: #213758; font-size: 13px; }
.mass-panel-heading span { color: #718096; font-size: 11px; }
.mass-control { width: 185px; }
.mass-value { min-width: 210px; flex: 1; }
.apply-mass-button { margin-bottom: 1px; }
.grid-scroll { overflow: auto; max-width: 100%; max-height: min(62vh, 680px); border: 1px solid #dce4ee; border-radius: 12px; background: #fff; box-shadow: 0 5px 20px rgb(31 55 85 / 5%); scrollbar-color: #94a3b8 #e9eef5; }
.edit-table { border-collapse: separate; border-spacing: 0; min-width: 1540px; width: 100%; text-align: left; font-size: 12px; }
.edit-table th, .edit-table td { height: 58px; padding: 9px 10px; border-bottom: 1px solid #e5ebf2; background: #fff; vertical-align: middle; }
.edit-table th { height: 46px; white-space: nowrap; background: #f3f6fa; color: #41546c; font-size: 11px; font-weight: 750; letter-spacing: .01em; position: sticky; top: 0; z-index: 3; }
.edit-table tbody tr:hover td { background: #f8fbff; }
.edit-table .select-column { position: sticky; left: 0; z-index: 2; width: 46px; min-width: 46px; text-align: center; }
.edit-table .equipment-column { position: sticky; left: 46px; z-index: 2; min-width: 210px; max-width: 250px; box-shadow: 8px 0 12px -12px rgb(31 55 85 / 55%); }
.edit-table th.select-column, .edit-table th.equipment-column { z-index: 5; background: #edf2f7; }
.edit-table .name { color: #213758; font-weight: 650; line-height: 1.35; }
.edit-table .name a { color: #245ea8; text-decoration: none; }
.edit-table .name a:hover { text-decoration: underline; }
.edit-table td.changed { background: #edf6ff; box-shadow: inset 0 0 0 1px #b9d7f7; }
.edit-table tbody tr:hover td.changed { background: #e8f3ff; }
.readonly-label { display: block; margin-top: 2px; color: #8795a8; font-size: 9px; font-weight: 600; text-transform: uppercase; }
.cell-control { width: 190px; min-width: 190px; max-width: 190px; }
.cell-select :deep(.searchable-select) { width: 100%; }
.cell-control :deep(.v-field), .mass-control :deep(.v-field) { background: rgb(var(--v-theme-surface)); }
.row-checkbox { display: inline-flex; vertical-align: middle; }
.row-checkbox :deep(.v-selection-control) { justify-content: center; }
.wp-multi-select { width: 245px; }
.mass-wp-select { max-width: 420px; }
.wp-multi-select :deep(.v-input__details), .mass-wp-select :deep(.v-input__details) { display: none; }
.wp-multi-select :deep(.v-field), .mass-wp-select :deep(.v-field) { border-radius: 8px; background: #fff; }
.wp-multi-select :deep(.v-field__input) { min-height: 40px; padding-top: 7px; padding-bottom: 7px; }
.wp-multi-select :deep(.selection-chip), .wp-multi-select :deep(.selection-summary) { font-weight: 400; }
.bulk-footer { position: sticky; bottom: 0; z-index: 7; justify-content: space-between; margin: 0 -16px -18px; padding: 12px 18px; border-top: 1px solid #dce4ee; background: rgb(255 255 255 / 96%); box-shadow: 0 -8px 22px rgb(31 55 85 / 7%); backdrop-filter: blur(8px); }
@media (max-width: 760px) {
  .bulk-editor { padding: 8px; }
  .edit-mode-header { align-items: flex-start; flex-direction: column; margin: -8px -8px 0; }
  .edit-status { justify-content: flex-start; }
  .mass-control { width: 100%; }
  .bulk-footer { margin: 0 -8px -8px; }
}
</style>
