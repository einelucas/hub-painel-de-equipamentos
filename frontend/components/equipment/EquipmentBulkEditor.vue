<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { onBeforeRouteLeave } from "vue-router";
import { VAlert, VBtn } from "vuetify/components";
import type { Equipment } from "~/types/equipment";

type Field = "disciplineId" | "responsibleUserId" | "eapNodeId" | "origin" |
  "startupAt" | "criticalityLabelId" | "workPackageIds";
type Operation = "SET" | "CLEAR" | "FILL_EMPTY" | "ADD" | "REMOVE" | "REPLACE";
interface Option { id: string; label: string }
interface CellChange { field: Field; operation: Operation; value?: string | string[] | null }
interface RowDraft { expectedUpdatedAt: string; changes: Partial<Record<Field, CellChange>> }
interface SelectionItem { equipmentId: string; expectedUpdatedAt: string }
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
const selected = ref<string[]>([]);
const versions = ref<Record<string, string>>({});
const drafts = ref<Record<string, RowDraft>>({});
const preview = ref<Preview | null>(null);
const previewRequest = ref<Record<string, unknown> | null>(null);
const state = ref<"idle" | "selecting" | "validating" | "saving">("idle");
const error = ref("");
const success = ref("");
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

watch(() => props.equipments, (items) => {
  for (const item of items) {
    if (!versions.value[item.id]) versions.value[item.id] = item.updatedAt;
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
function cellChanged(row: Equipment, field: Field, event: Event): void {
  const value = (event.target as HTMLInputElement | HTMLSelectElement).value;
  if (value === baseValue(row, field)) {
    const current = drafts.value[row.id];
    if (current) {
      delete current.changes[field];
      if (!Object.keys(current.changes).length) delete drafts.value[row.id];
      drafts.value = { ...drafts.value };
    }
    return;
  }
  setChange(row.id, field, value ? "SET" : "CLEAR", value || null, row.updatedAt);
}
function wpChanged(row: Equipment, event: Event): void {
  const chosen = Array.from((event.target as HTMLSelectElement).selectedOptions)
    .map((option) => option.value);
  setChange(row.id, "workPackageIds", "REPLACE", chosen, row.updatedAt);
}
function toggle(row: Equipment): void {
  versions.value[row.id] = versions.value[row.id] ?? row.updatedAt;
  selected.value = selected.value.includes(row.id)
    ? selected.value.filter((id) => id !== row.id)
    : [...selected.value, row.id];
}
function selectPage(): void {
  const ids = props.equipments.map((row) => row.id);
  selected.value = [...new Set([...selected.value, ...ids])];
}
async function selectAllFiltered(): Promise<void> {
  if (busy.value) return;
  if (editing.value && !window.confirm("Manter rascunho e substituir seleção pelos resultados filtrados?")) {
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
    }
    selected.value = result.items.map((item) => item.equipmentId);
    success.value = `Selecionados ${result.total} equipamentos em todas as páginas filtradas.`;
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "Falha ao selecionar.";
  } finally { state.value = "idle"; }
}
function massChanged(event: Event): void {
  massField.value = (event.target as HTMLSelectElement).value as Field;
  massValue.value = "";
  massWpIds.value = [];
  massOp.value = massField.value === "workPackageIds" ? "ADD" : "SET";
}
function massWpChanged(event: Event): void {
  massWpIds.value = Array.from((event.target as HTMLSelectElement).selectedOptions)
    .map((option) => option.value);
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
function discard(): void {
  if (editing.value && !window.confirm("Descartar todas as alterações não salvas?")) return;
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
onBeforeRouteLeave(() => !editing.value || window.confirm("Descartar alterações pendentes?"));
defineExpose({ hasPending: () => editing.value, confirmDiscard: () => !editing.value ||
  window.confirm("Descartar alterações pendentes?") });
</script>

<template>
  <div class="bulk-editor" data-testid="equipment-bulk-editor" :aria-busy="busy">
    <div class="bulk-actions">
      <strong>Modo de edição · {{ pendingCount }} campo(s) pendente(s)</strong>
      <span class="spacer" />
      <VBtn size="small" variant="tonal" :disabled="busy" @click="selectPage">Selecionar página</VBtn>
      <VBtn size="small" variant="tonal" :loading="state === 'selecting'" :disabled="busy"
        @click="selectAllFiltered">Todos os filtrados ({{ total }})</VBtn>
      <VBtn size="small" variant="text" :disabled="busy" @click="selected = []">Limpar seleção</VBtn>
    </div>
    <p v-if="selected.length" class="muted">{{ selected.length }} linha(s) selecionada(s).</p>
    <div v-if="selected.length" class="mass-panel">
      <label>Campo
        <select :value="massField" :disabled="busy" @change="massChanged">
          <option v-for="field in fields" :key="field.key" :value="field.key">{{ field.label }}</option>
        </select>
      </label>
      <label>Operação
        <select v-model="massOp" :disabled="busy">
          <template v-if="massField === 'workPackageIds'">
            <option value="ADD">Adicionar</option><option value="REMOVE">Remover</option>
            <option value="REPLACE">Substituir</option><option value="CLEAR">Limpar</option>
          </template>
          <template v-else>
            <option value="SET">Substituir</option><option value="FILL_EMPTY">Preencher vazios</option>
            <option value="CLEAR">Limpar</option>
          </template>
        </select>
      </label>
      <label v-if="massOp !== 'CLEAR'">Novo valor
        <select v-if="massField === 'workPackageIds'" multiple size="3" :disabled="busy"
          aria-label="Work Packages em massa" @change="massWpChanged">
          <option v-for="option in workPackageOptions" :key="option.id" :value="option.id">
            {{ option.label }}
          </option>
        </select>
        <select v-else-if="['disciplineId','responsibleUserId','eapNodeId','criticalityLabelId'].includes(massField)"
          v-model="massValue" :disabled="busy">
          <option value="">Escolher</option>
          <option v-for="option in options(massField)" :key="option.id" :value="option.id">
            {{ option.label }}
          </option>
        </select>
        <input v-else v-model="massValue" :type="massField === 'startupAt' ? 'date' : 'text'"
          :disabled="busy" />
      </label>
      <VBtn color="primary" size="small" variant="tonal" :disabled="busy" @click="applyMass">
        Aplicar ao rascunho
      </VBtn>
    </div>
    <VAlert v-if="error" type="error" variant="tonal" density="compact" role="alert">{{ error }}</VAlert>
    <VAlert v-if="success" type="success" variant="tonal" density="compact">{{ success }}</VAlert>
    <div class="grid-scroll">
      <table class="edit-table">
        <thead><tr>
          <th><span class="sr-only">Selecionar</span></th>
          <th>Equipamento (somente leitura)</th>
          <th v-for="field in fields" :key="field.key">{{ field.label }}</th>
          <th>Etapa (somente leitura)</th>
        </tr></thead>
        <tbody>
          <tr v-for="row in equipments" :key="row.id">
            <td><input type="checkbox" :checked="selected.includes(row.id)" :disabled="busy"
              :aria-label="`Selecionar ${row.name}`" @change="toggle(row)" /></td>
            <td class="name"><NuxtLink :to="`/equipamentos/${row.id}`">{{ row.name }}</NuxtLink></td>
            <td v-for="field in fields" :key="field.key"
              :class="{ changed: Boolean(drafts[row.id]?.changes[field.key]) }">
              <select v-if="field.kind === 'select'" :value="draftValue(row, field.key)"
                :disabled="busy" :aria-label="`${field.label}: ${row.name}`"
                @change="cellChanged(row, field.key, $event)">
                <option value="">—</option>
                <option v-for="option in options(field.key)" :key="option.id" :value="option.id">
                  {{ option.label }}
                </option>
              </select>
              <select v-else-if="field.kind === 'wps'" multiple size="2" :disabled="busy"
                :aria-label="`Work Packages: ${row.name}`" @change="wpChanged(row, $event)">
                <option v-for="option in workPackageOptions" :key="option.id"
                  :value="option.id"
                  :selected="(draftValue(row, field.key) as string[]).includes(option.id)">
                  {{ option.label }}
                </option>
              </select>
              <input v-else :value="draftValue(row, field.key)"
                :type="field.kind === 'date' ? 'date' : 'text'"
                :disabled="busy" :aria-label="`${field.label}: ${row.name}`"
                @change="cellChanged(row, field.key, $event)" />
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
        <VBtn color="primary" variant="flat" :loading="state === 'validating'"
          :disabled="!editing || busy" @click="review">Revisar alterações</VBtn>
      </div>
    </div>
    <BulkEditReviewDialog :preview="preview" :saving="state === 'saving'"
      @close="preview = null" @confirm="save" />
  </div>
</template>

<style scoped>
.bulk-editor { padding: 8px 16px 18px; display: grid; gap: 12px; }
.bulk-actions, .bulk-footer, .footer-buttons { display: flex; flex-wrap: wrap; align-items: center; gap: 9px; }
.bulk-actions strong { color: #213758; font-size: 13px; }
.spacer { flex: 1; }
.muted, .bulk-footer span { font-size: 12px; color: #64748b; }
.mass-panel { display: flex; align-items: end; flex-wrap: wrap; gap: 10px; background: #f1f5f9;
  border-radius: 10px; padding: 12px; }
.mass-panel label { display: grid; gap: 5px; font-size: 12px; color: #475569; }
input, select { background: white; border: 1px solid #cbd5e1; padding: 7px 8px; border-radius: 6px;
  min-width: 95px; max-width: 215px; color: #213758; font: inherit; }
select[multiple] { min-width: 145px; }
input:focus, select:focus { outline: 2px solid #3b82f6; outline-offset: 1px; }
.grid-scroll { overflow-x: auto; max-width: 100%; }
.edit-table { border-collapse: collapse; text-align: left; width: 100%; font-size: 12px; }
.edit-table th, .edit-table td { padding: 9px; border-bottom: 1px solid #e2e8f0; }
.edit-table th { white-space: nowrap; background: #f8fafc; position: sticky; top: 0; }
.edit-table .name { min-width: 180px; color: #213758; font-weight: 600; }
.edit-table td.changed { background: #eff6ff; }
.bulk-footer { justify-content: space-between; border-top: 1px solid #e2e8f0; padding-top: 12px; }
@media (max-width: 760px) {
  .bulk-editor { padding: 8px; }
  .mass-panel label { width: 100%; }
  input, select { max-width: 100%; }
}
</style>
