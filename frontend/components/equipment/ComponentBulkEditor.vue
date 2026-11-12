<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { onBeforeRouteLeave } from "vue-router";
import { VAlert, VBtn } from "vuetify/components";
import type { EquipmentComponent } from "~/types/equipment";

type Field = "tag" | "sector" | "startupAt" | "leadTimeDays" |
  "preStartDays" | "contractDeliveryAt" | "freightDays";
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
const selected = ref<string[]>([]);
const drafts = ref<Record<string, Draft>>({});
const preview = ref<Preview | null>(null);
const previewRequest = ref<Record<string, unknown> | null>(null);
const state = ref<"idle" | "validating" | "saving">("idle");
const error = ref("");
const success = ref("");
const massField = ref<Field>("sector");
const massOp = ref<Operation>("SET");
const massValue = ref("");
const columns: { key: Field; label: string; kind: "text" | "date" | "number" }[] = [
  { key: "tag", label: "TAG", kind: "text" },
  { key: "sector", label: "Setor", kind: "text" },
  { key: "startupAt", label: "Startup", kind: "date" },
  { key: "leadTimeDays", label: "Lead time", kind: "number" },
  { key: "preStartDays", label: "Pré-start", kind: "number" },
  { key: "contractDeliveryAt", label: "Entrega contratual", kind: "date" },
  { key: "freightDays", label: "Frete", kind: "number" },
];
const massFields = columns.filter((column) => column.key !== "tag");
const massKind = computed(() => massFields.find((item) => item.key === massField.value)?.kind ?? "text");
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
function setCell(component: EquipmentComponent, column: typeof columns[number], event: Event): void {
  const raw = (event.target as HTMLInputElement).value;
  if (raw === baseValue(component, column.key)) {
    const data = drafts.value[component.id];
    if (data) {
      delete data.changes[column.key];
      if (!Object.keys(data.changes).length) delete drafts.value[component.id];
      drafts.value = { ...drafts.value };
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
function toggle(id: string): void {
  selected.value = selected.value.includes(id)
    ? selected.value.filter((item) => item !== id)
    : [...selected.value, id];
}
function massFieldChanged(event: Event): void {
  massField.value = (event.target as HTMLSelectElement).value as Field;
  massValue.value = "";
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
function discard(): void {
  if (pendingCount.value && !window.confirm("Descartar alterações pendentes?")) return;
  drafts.value = {};
  emit("exit");
}
function beforeUnload(event: BeforeUnloadEvent): void {
  if (pendingCount.value) event.preventDefault();
}
onMounted(() => window.addEventListener("beforeunload", beforeUnload));
onBeforeUnmount(() => window.removeEventListener("beforeunload", beforeUnload));
onBeforeRouteLeave(() => !pendingCount.value || window.confirm("Descartar alterações pendentes?"));
defineExpose({ hasPending: () => pendingCount.value > 0,
  confirmDiscard: () => !pendingCount.value || window.confirm("Descartar alterações?") });
</script>

<template>
  <div class="component-bulk" :aria-busy="busy" data-testid="component-bulk-editor">
    <div class="toolbar">
      <strong>Modo de edição · {{ pendingCount }} campo(s) pendente(s)</strong>
      <VBtn variant="tonal" size="small" :disabled="busy"
        @click="selected = components.map((row) => row.id)">Selecionar todos</VBtn>
      <VBtn variant="text" size="small" :disabled="busy"
        @click="selected = []">Limpar seleção</VBtn>
    </div>
    <div v-if="selected.length" class="mass-panel">
      <strong>{{ selected.length }} selecionado(s)</strong>
      <label>Campo
        <select :value="massField" :disabled="busy" @change="massFieldChanged">
          <option v-for="column in massFields" :key="column.key" :value="column.key">
            {{ column.label }}
          </option>
        </select>
      </label>
      <label>Operação
        <select v-model="massOp" :disabled="busy">
          <option value="SET">Substituir</option>
          <option value="FILL_EMPTY">Preencher vazios</option>
          <option value="CLEAR">Limpar</option>
        </select>
      </label>
      <label v-if="massOp !== 'CLEAR'">Valor
        <input v-model="massValue" :type="massKind === 'date' ? 'date' :
          massKind === 'number' ? 'number' : 'text'" :min="massKind === 'number' ? 0 : undefined"
          :disabled="busy" />
      </label>
      <VBtn variant="tonal" color="primary" size="small" :disabled="busy"
        @click="applyMass">Aplicar ao rascunho</VBtn>
    </div>
    <VAlert v-if="error" type="error" density="compact" variant="tonal" role="alert">
      {{ error }}
    </VAlert>
    <VAlert v-if="success" type="success" density="compact" variant="tonal">
      {{ success }}
    </VAlert>
    <div class="table-scroll">
      <table class="edit-table">
        <thead><tr>
          <th>Selecionar</th><th>Componente (somente leitura)</th>
          <th v-for="column in columns" :key="column.key">{{ column.label }}</th>
        </tr></thead>
        <tbody>
          <tr v-for="component in components" :key="component.id">
            <td><input type="checkbox" :checked="selected.includes(component.id)"
              :disabled="busy" :aria-label="`Selecionar ${component.name}`"
              @change="toggle(component.id)" /></td>
            <td class="name">{{ component.name }}</td>
            <td v-for="column in columns" :key="column.key"
              :class="{ changed: Boolean(drafts[component.id]?.changes[column.key]) }">
              <input :type="column.kind" :value="currentValue(component, column.key)"
                :min="column.kind === 'number' ? 0 : undefined"
                :aria-label="`${column.label}: ${component.name}`" :disabled="busy"
                @change="setCell(component, column, $event)" />
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <div class="footer">
      <span>{{ state === "validating" ? "Validando…" :
        state === "saving" ? "Gravando lote…" : "Altere células ou selecione componentes" }}</span>
      <VBtn variant="text" :disabled="busy" @click="discard">Sair da edição</VBtn>
      <VBtn variant="flat" color="primary" :loading="state === 'validating'"
        :disabled="!pendingCount || busy" @click="review">Revisar alterações</VBtn>
    </div>
    <BulkEditReviewDialog :preview="preview" :saving="state === 'saving'"
      @close="preview = null" @confirm="save" />
  </div>
</template>

<style scoped>
.component-bulk { display: grid; gap: 12px; padding: 14px; }
.toolbar, .mass-panel, .footer { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
.toolbar strong, .mass-panel strong { font-size: 13px; color: #213758; margin-right: auto; }
.mass-panel { background: #f1f5f9; border-radius: 10px; padding: 12px; }
.mass-panel label { font-size: 12px; display: grid; gap: 5px; color: #475569; }
input, select { background: #fff; color: #213758; border: 1px solid #cbd5e1; border-radius: 6px;
  padding: 7px; max-width: 180px; min-width: 95px; font: inherit; }
input:focus, select:focus { outline: 2px solid #3b82f6; outline-offset: 1px; }
.table-scroll { overflow-x: auto; }
.edit-table { border-collapse: collapse; width: 100%; text-align: left; font-size: 12px; }
.edit-table th, .edit-table td { border-bottom: 1px solid #e2e8f0; padding: 8px 9px; }
.edit-table th { background: #f8fafc; white-space: nowrap; }
.edit-table .name { font-weight: 600; min-width: 180px; }
.edit-table td.changed { background: #eff6ff; }
.footer { justify-content: flex-end; border-top: 1px solid #e2e8f0; padding-top: 12px; }
.footer span { margin-right: auto; color: #64748b; font-size: 12px; }
@media (max-width: 760px) {
  .component-bulk { padding: 8px; }
  .mass-panel label { width: 100%; }
  .mass-panel input, .mass-panel select { max-width: 100%; }
}
</style>
