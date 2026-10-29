<script setup lang="ts">
import Button from "~/components/ui/Button.vue";
import { VAutocomplete } from "vuetify/components/VAutocomplete";
import { computed, ref, watch } from "vue";
import { Check, ChevronDown, ChevronRight, Search } from "lucide-vue-next";

interface Area { id: string; name: string; isUnassigned: boolean; active: boolean }
interface ComponentOption { id: string; name: string; active: boolean; requiresQuantityReview: boolean; requiresNameReview: boolean }
interface EquipmentModel { id: string; name: string; areaIds: string[]; components: ComponentOption[]; active: boolean; reviewFlags: string[] }
interface MasterCatalog { areas: Area[]; equipments: EquipmentModel[] }
interface Unit { id: string; name: string; active: boolean }
interface CatalogList<T> { items: T[] }
interface Created { projectContextId: string; equipmentsCreated: number; componentsCreated: number; alreadyCreated: boolean }

const props = defineProps<{ open: boolean; initialUnitId?: string }>();
const emit = defineEmits<{ close: [] }>();
const api = useApi();
const context = useModuleContextStore();
const loading = ref(false);
const saving = ref(false);
const error = ref("");
const step = ref(0);
const units = ref<Unit[]>([]);
const unitId = ref("");
const unitOptions = computed(() => [
  { title: "Selecionar unidade", value: "" },
  ...units.value.map((unit) => ({ title: unit.name, value: unit.id })),
]);
const name = ref("");
const code = ref("");
const search = ref("");
const catalog = ref<MasterCatalog>({ areas: [], equipments: [] });
const selected = ref<Record<string, string[]>>({});
const expandedAreas = ref<Record<string, boolean>>({});
const requestId = ref("");
const created = ref<Created | null>(null);
const STEPS = ["Dados da obra", "Equipamentos", "Componentes", "Revisão"];

watch(() => props.open, async (open) => {
  if (!open) return;
  step.value = 0;
  name.value = "";
  code.value = "";
  selected.value = {};
  expandedAreas.value = {};
  search.value = "";
  created.value = null;
  requestId.value = "";
  loading.value = true;
  error.value = "";
  try {
    const [unitData, masterData] = await Promise.all([
      api.get<CatalogList<Unit>>("/units"),
      api.get<MasterCatalog>("/master-catalog"),
    ]);
    units.value = unitData.items;
    unitId.value = units.value.find((u) => u.id === props.initialUnitId)?.id ?? units.value[0]?.id ?? "";
    catalog.value = masterData;
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "Falha ao carregar o catálogo mestre.";
  } finally {
    loading.value = false;
  }
});

const selectedIds = computed(() => Object.keys(selected.value));
const totalComponents = computed(() => Object.values(selected.value).reduce((sum, ids) => sum + ids.length, 0));
const modelById = computed(() => new Map(catalog.value.equipments.map((item) => [item.id, item])));
const selectedModels = computed(() => selectedIds.value.map((id) => modelById.value.get(id)).filter((item): item is EquipmentModel => Boolean(item)));
const areas = computed(() => catalog.value.areas.filter((area) => area.active));
const areasWithResults = computed(() => areas.value.map((area) => ({
  ...area,
  models: catalog.value.equipments.filter((model) =>
    model.active && model.areaIds.includes(area.id)
    && model.name.toLocaleLowerCase("pt-BR").includes(search.value.toLocaleLowerCase("pt-BR").trim()),
  ),
})).filter((area) => area.models.length));
const withoutArea = computed(() => catalog.value.equipments.filter(
  (item) => item.active && !item.areaIds.length && item.name.toLocaleLowerCase("pt-BR").includes(search.value.toLocaleLowerCase("pt-BR").trim()),
));
const canContinue = computed(() => (step.value === 0 ? Boolean(unitId.value && name.value.trim()) : true));
function selectedEquipment(id: string): boolean { return Object.prototype.hasOwnProperty.call(selected.value, id); }
function toggleEquipment(id: string): void {
  const next = { ...selected.value };
  if (Object.prototype.hasOwnProperty.call(next, id)) {
    selected.value = Object.fromEntries(Object.entries(next).filter(([key]) => key !== id));
    return;
  }
  next[id] = [];
  selected.value = next;
}
function componentSelected(equipmentId: string, componentId: string): boolean {
  return (selected.value[equipmentId] ?? []).includes(componentId);
}
function toggleComponent(equipmentId: string, componentId: string): void {
  const current = selected.value[equipmentId] ?? [];
  selected.value = {
    ...selected.value,
    [equipmentId]: current.includes(componentId) ? current.filter((id) => id !== componentId) : [...current, componentId],
  };
}
function allComponents(equipment: EquipmentModel, active: boolean): void {
  selected.value = {
    ...selected.value,
    [equipment.id]: active ? equipment.components.filter((c) => c.active).map((c) => c.id) : [],
  };
}
function next(): void {
  error.value = "";
  if (!canContinue.value) { error.value = "Informe a unidade e o nome da obra."; return; }
  step.value = Math.min(step.value + 1, 3);
}
function previous(): void { error.value = ""; step.value = Math.max(step.value - 1, 0); }
function close(): void { if (!saving.value) emit("close"); }

async function submit(): Promise<void> {
  if (saving.value || !unitId.value || !name.value.trim()) return;
  saving.value = true;
  error.value = "";
  // Mesma chave em retries, evitando criação duplicada após timeout.
  if (!requestId.value) requestId.value = crypto.randomUUID();
  try {
    const result = await api.post<Created>("/master-catalog/projects", {
      requestId: requestId.value,
      unitId: unitId.value,
      name: name.value.trim(),
      code: code.value.trim() || null,
      selections: selectedModels.value.map((equipment) => ({
        equipmentId: equipment.id, componentIds: selected.value[equipment.id] ?? [],
      })),
    });
    created.value = result;
    await context.setUnit(unitId.value);
    await context.setProjectContext(result.projectContextId);
    await navigateTo({ path: "/equipamentos", query: { unit: unitId.value, project: result.projectContextId } });
    emit("close");
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "Não foi possível criar a obra.";
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <AppModal :open="open" title="Nova obra" size="wide" :busy="saving" @close="close">
    <div class="project-wizard" data-testid="new-project-wizard">
      <ol class="steps" aria-label="Etapas de criação de obra">
        <li v-for="(item, index) in STEPS" :key="item" :class="{ current: index === step, done: index < step }">
          <span class="number"><Check v-if="index < step" :size="13" /><template v-else>{{ index + 1 }}</template></span>
          <span>{{ item }}</span>
        </li>
      </ol>
      <p v-if="error" class="message error" role="alert">{{ error }}</p>
      <p v-if="loading" class="message" role="status">Carregando unidades e catálogo mestre...</p>
      <template v-else>
        <section v-if="step === 0" class="step-body">
          <h3>Identificação da obra</h3>
          <p>Selecione a unidade e informe o nome do novo projeto.</p>
          <div class="project-unit">
            <VAutocomplete
              v-model="unitId"
              :items="unitOptions"
              item-title="title"
              item-value="value"
              data-testid="new-project-unit"
              variant="outlined"
              color="primary"
              density="comfortable"
              hide-details="auto"
              label="Unidade"
            />
          </div>
          <label>Nome da obra
            <input v-model="name" maxlength="160" placeholder="Ex.: Ampliação da unidade" data-testid="new-project-name" />
          </label>
          <label>Código (opcional)
            <input v-model="code" maxlength="60" placeholder="Código da obra" />
          </label>
        </section>
        <section v-else-if="step === 1" class="step-body">
          <div class="section-title"><div><h3>Selecione os equipamentos</h3><p>Um mesmo modelo pode aparecer em várias áreas sem ser duplicado.</p></div><strong>{{ selectedIds.length }} selecionados</strong></div>
          <div class="search"><Search :size="16" /><input v-model="search" placeholder="Buscar por nome do equipamento" aria-label="Buscar equipamento" /></div>
          <div v-if="!catalog.equipments.length" class="empty">
            <p>O Catálogo Mestre ainda não possui equipamentos.</p>
            <NuxtLink to="/administracao/catalogo-mestre" @click="close">Administrar catálogo e carregar seed</NuxtLink>
          </div>
          <div v-else class="areas-list">
            <div v-for="area in areasWithResults" :key="area.id" class="area-group">
              <button type="button" class="area-title" @click="expandedAreas[area.id] = expandedAreas[area.id] === false">
                <ChevronRight v-if="expandedAreas[area.id] === false" :size="16" /><ChevronDown v-else :size="16" />
                {{ area.name }} <small>{{ area.models.length }}</small>
              </button>
              <div v-if="expandedAreas[area.id] !== false" class="equipment-list">
                <label v-for="equipment in area.models" :key="equipment.id" class="check-row">
                  <input type="checkbox" :checked="selectedEquipment(equipment.id)" @change="toggleEquipment(equipment.id)" />
                  <span>{{ equipment.name }}</span>
                  <small>{{ equipment.components.length }} comp.</small>
                </label>
              </div>
            </div>
            <div v-if="withoutArea.length" class="area-group">
              <div class="area-title">Sem área definida <small>{{ withoutArea.length }}</small></div>
              <div class="equipment-list">
                <label v-for="equipment in withoutArea" :key="equipment.id" class="check-row">
                  <input type="checkbox" :checked="selectedEquipment(equipment.id)" @change="toggleEquipment(equipment.id)" />
                  <span>{{ equipment.name }}</span>
                </label>
              </div>
            </div>
          </div>
        </section>
        <section v-else-if="step === 2" class="step-body">
          <div class="section-title"><div><h3>Escolha os componentes</h3><p>Todos começam desmarcados. Você pode criar equipamentos sem componentes.</p></div><strong>{{ totalComponents }} selecionados</strong></div>
          <p v-if="!selectedModels.length" class="empty">Nenhum equipamento selecionado. Volte para adicionar equipamentos ou prossiga com a obra vazia.</p>
          <div v-for="equipment in selectedModels" :key="equipment.id" class="area-group">
            <div class="area-title">{{ equipment.name }} <small>{{ (selected[equipment.id] ?? []).length }}/{{ equipment.components.length }}</small></div>
            <div class="component-actions">
              <Button type="button" variant="ghost" @click="allComponents(equipment, true)">Selecionar todos</Button>
              <Button type="button" variant="ghost" @click="allComponents(equipment, false)">Limpar</Button>
            </div>
            <p v-if="!equipment.components.length" class="hint">Sem componentes cadastrados no catálogo.</p>
            <div class="equipment-list">
              <label v-for="component in equipment.components.filter(c => c.active)" :key="component.id" class="check-row">
                <input
type="checkbox" :checked="componentSelected(equipment.id, component.id)"
                  @change="toggleComponent(equipment.id, component.id)" />
                <span>{{ component.name }}</span>
                <small v-if="component.requiresQuantityReview || component.requiresNameReview">Revisar</small>
              </label>
            </div>
          </div>
        </section>
        <section v-else class="step-body">
          <h3>Revise antes de criar</h3>
          <p><strong>Unidade:</strong> {{ units.find(u => u.id === unitId)?.name }}</p>
          <p><strong>Obra:</strong> {{ name }} <template v-if="code">({{ code }})</template></p>
          <p><strong>{{ selectedModels.length }} equipamentos · {{ totalComponents }} componentes</strong></p>
          <div v-for="equipment in selectedModels" :key="equipment.id" class="review-line">
            <strong>{{ equipment.name }}</strong>
            <span>{{ (selected[equipment.id] ?? []).length }} componentes</span>
            <ul><li v-for="component in equipment.components.filter(c => componentSelected(equipment.id, c.id))" :key="component.id">{{ component.name }}</li></ul>
          </div>
          <p class="hint">TAGs, EAP, prazos, fornecedores e demais informações operacionais serão preenchidos depois na obra.</p>
        </section>
        <footer class="wizard-footer">
          <Button type="button" :disabled="saving" variant="outline" @click="step === 0 ? close() : previous()">{{ step === 0 ? "Cancelar" : "Voltar" }}</Button>
          <Button v-if="step < 3" type="button" :disabled="!canContinue" variant="default" @click="next">Continuar</Button>
          <Button v-else type="button" :disabled="saving" data-testid="create-project-submit" variant="default" :loading="saving" @click="submit">{{ saving ? "Criando..." : "Criar obra" }}</Button>
        </footer>
      </template>
    </div>
  </AppModal>
</template>

<style scoped>
.project-wizard { display: flex; flex-direction: column; gap: 18px; color: #273e5a; min-height: 350px; max-height: min(76vh, 730px); }
.steps { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin: 0; padding: 0; list-style: none; }
.steps li { display: flex; gap: 7px; align-items: center; font-size: 12px; color: #8190a3; font-weight: 650; }
.steps li.current, .steps li.done { color: #304f7e; }
.number { display: grid; place-items: center; height: 24px; width: 24px; flex-shrink: 0; border-radius: 50%; border: 1px solid #dce4ef; }
.current .number, .done .number { background: #e8f1fc; border-color: #8ca9d0; }
.step-body { min-height: 0; overflow-y: auto; display: flex; flex-direction: column; gap: 12px; padding: 2px 4px; }
.step-body h3 { font-size: 16px; font-weight: 800; margin: 0; }
.step-body p { margin: 0; font-size: 13px; color: #677b92; }
.step-body label:not(.check-row) { display: grid; gap: 6px; font-size: 12px; font-weight: 700; }
.step-body input:not([type=checkbox]):not([role=combobox]), .step-body select { width: 100%; border: 1px solid #dce4ef; border-radius: 9px; padding: 10px 12px; background: #fff; color: #273e5a; }
.section-title { display: flex; justify-content: space-between; gap: 15px; align-items: center; }
.section-title strong { font-size: 12px; white-space: nowrap; }
.search { position: relative; display: flex; align-items: center; gap: 8px; border: 1px solid #dce4ef; border-radius: 10px; padding-left: 10px; }
.search input { border: none !important; outline: none; }
.areas-list { display: grid; gap: 10px; }
.area-group { border: 1px solid #e0e7f1; border-radius: 11px; overflow: hidden; margin-bottom: 2px; }
.area-title { display: flex; gap: 8px; align-items: center; width: 100%; border: 0; padding: 12px 14px; background: #f3f6fb; color: #273e5a; text-align: left; font-size: 13px; font-weight: 800; }
.area-title small, .check-row small { margin-left: auto; font-size: 11px; color: #75849b; font-weight: 600; }
.equipment-list { padding: 6px 12px; display: grid; gap: 2px; }
.check-row { display: flex; align-items: center; gap: 10px; border-radius: 7px; padding: 7px 6px; font-size: 13px; cursor: pointer; }
.check-row:hover { background: #f6f8fb; }
.check-row input { width: 16px; height: 16px; accent-color: #304f7e; }
.component-actions { display: flex; gap: 14px; padding: 8px 12px 0; }

.review-line { padding: 10px 14px; border: 1px solid #e0e7f1; border-radius: 9px; display: grid; gap: 4px; font-size: 13px; }
.review-line > span { color: #75849b; }
.review-line ul { margin: 4px 0 0 15px; padding: 0; color: #677b92; font-size: 12px; }
.empty { padding: 22px; background: #f3f6fb; border-radius: 10px; }
.hint { font-size: 12px; color: #71849a; padding: 8px 12px; }
.message { font-size: 13px; color: #476789; }
.error { padding: 10px; color: #a43e33; background: #fff2f0; border-radius: 9px; }
.wizard-footer { display: flex; justify-content: flex-end; gap: 10px; padding-top: 12px; border-top: 1px solid #e0e7f1; }




@media (max-width: 660px) { .steps { grid-template-columns: repeat(2, 1fr); } .project-wizard { max-height: 78vh; } }
</style>
