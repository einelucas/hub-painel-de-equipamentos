<script setup lang="ts">
import { VAlert, VBtn, VCard, VCardActions, VCardText, VCardTitle, VDialog, VProgressLinear, VTextField, VCombobox } from "vuetify/components";
import { mdiContentCopy, mdiContentSave, mdiDeleteOutline, mdiFileExcelOutline, mdiPlus } from "@mdi/js";
import { FileText, Handshake, PackageCheck } from "lucide-vue-next";
import NavigationMenu from "~/components/ui/NavigationMenu.vue";
import type {
  SimulationProject, SimulationProjectList, SimulationUnit, SimulationUnitList,
  StartupItemInput, StartupMetric, StartupScenario, StartupScenarioList,
} from "~/types/startupSimulation";
import { asDraftItems, previewScenario } from "~/utils/startupSimulation";
import { readStartupWorkbook } from "~/utils/startupWorkbook";
import { exportStartupScenarios } from "~/utils/startupExport";

definePageMeta({ middleware: "auth" });

const api = useApi();
const auth = useAuthStore();
const confirm = useConfirm();
const canRead = computed(() => auth.can("equipments:read"));
const canWrite = computed(() => auth.can("equipments:write"));

const scenarios = ref<StartupScenario[]>([]);
const loading = ref(false);
const busy = ref(false);
const error = ref("");
const notice = ref("");
const importWarnings = ref<string[]>([]);
const activeId = ref("");
const leftId = ref("");
const rightId = ref("");
const draftName = ref("");
const draftStartup = ref("");
const draftRows = ref<StartupItemInput[]>([]);
const metric = ref<StartupMetric>("negotiations");
const metricNavigationItems = [
  { value: "negotiations", label: "Negociação", icon: Handshake },
  { value: "contracts", label: "Contrato/OC", icon: FileText },
  { value: "deliveries", label: "Entrega", icon: PackageCheck },
];
const search = ref("");
const monthFilter = ref("");
const fileInput = ref<HTMLInputElement | null>(null);
const createDialog = ref(false);
const creatingClone = ref(false);
const newName = ref("");
const newStartup = ref("");
const units = ref<SimulationUnit[]>([]);
const projects = ref<SimulationProject[]>([]);
const selectedUnitId = ref("");
const selectedProjectId = ref("");
const scopesLoading = ref(false);
const scopeDialog = ref<"" | "unit" | "project">("");
const scopeName = ref("");
const addEquipmentDialog = ref(false);
const equipmentName = ref("");
const equipmentOrigin = ref("");
const equipmentDiscipline = ref("");
const equipmentSupplier = ref("");
const equipmentArea = ref("");
const equipmentResponsible = ref("");

async function loadScopes(preferredUnitId = ""): Promise<void> {
  scopesLoading.value = true;
  error.value = "";
  try {
    units.value = (await api.get<SimulationUnitList>("/startup-simulation-units")).items;
    selectedUnitId.value = units.value.find(u => u.id === preferredUnitId)?.id
      ?? units.value.find(u => u.id === selectedUnitId.value)?.id
      ?? units.value[0]?.id ?? "";
    await loadProjects();
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "Não foi possível consultar as unidades do simulador.";
  } finally {
    scopesLoading.value = false;
  }
}

async function loadProjects(preferredProjectId = ""): Promise<void> {
  if (!selectedUnitId.value) {
    projects.value = [];
    selectedProjectId.value = "";
    await reload();
    return;
  }
  const unitId = selectedUnitId.value;
  scopesLoading.value = true;
  try {
    const response = await api.get<SimulationProjectList>("/startup-simulation-projects", { unit_id: unitId });
    if (unitId !== selectedUnitId.value) return;
    projects.value = response.items;
    selectedProjectId.value = projects.value.find(p => p.id === preferredProjectId)?.id
      ?? projects.value.find(p => p.id === selectedProjectId.value)?.id
      ?? projects.value[0]?.id ?? "";
    await reload();
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "Não foi possível consultar as obras do simulador.";
  } finally {
    if (unitId === selectedUnitId.value) scopesLoading.value = false;
  }
}

async function discardBeforeSwitch(): Promise<boolean> {
  if (!dirty.value) return true;
  return confirm.confirm({
    title: "Alterações não salvas",
    message: "Descartar as alterações deste cenário?",
    detail: "As datas e os prazos não salvos serão perdidos.",
    confirmLabel: "Descartar alterações", tone: "danger", icon: "warning",
  });
}

async function chooseUnit(id: string): Promise<void> {
  if (id === selectedUnitId.value || !await discardBeforeSwitch()) return;
  selectedUnitId.value = id;
  selectedProjectId.value = "";
  await loadProjects();
}

async function chooseProject(id: string): Promise<void> {
  if (id === selectedProjectId.value || !await discardBeforeSwitch()) return;
  selectedProjectId.value = id;
  await reload();
}

async function chooseScenario(id: string): Promise<void> {
  if (id === activeId.value || !await discardBeforeSwitch()) return;
  selectActive(id);
}

function openScopeDialog(mode: "unit" | "project"): void {
  if (!canWrite.value || (mode === "project" && !selectedUnitId.value)) return;
  scopeName.value = "";
  scopeDialog.value = mode;
}

async function createScope(): Promise<void> {
  if (!scopeName.value.trim() || !canWrite.value || !scopeDialog.value) return;
  busy.value = true;
  error.value = "";
  try {
    const body = { name: scopeName.value.trim() };
    if (scopeDialog.value === "unit") {
      const created = await api.post<SimulationUnit>("/startup-simulation-units", body);
      await loadScopes(created.id);
      notice.value = "Unidade criada no simulador.";
    } else {
      const created = await api.post<SimulationProject>(
        `/startup-simulation-projects?unit_id=${encodeURIComponent(selectedUnitId.value)}`, body,
      );
      await loadProjects(created.id);
      notice.value = "Obra criada no simulador.";
    }
    scopeDialog.value = "";
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "Não foi possível criar o cadastro.";
  } finally {
    busy.value = false;
  }
}

async function deleteScope(mode: "unit" | "project"): Promise<void> {
  if (!canWrite.value) return;
  const id = mode === "unit" ? selectedUnitId.value : selectedProjectId.value;
  const name = mode === "unit" ? units.value.find(u => u.id === id)?.name
    : projects.value.find(p => p.id === id)?.name;
  if (!id || !name) return;
  if (!await discardBeforeSwitch()) return;
  const label = mode === "unit" ? "unidade" : "obra";
  const agreed = await confirm.confirm({
    title: `Excluir ${label} do simulador`,
    message: `Excluir ${label} "${name}"?`,
    detail: "O cadastro só poderá ser excluído se não possuir obras ou simulações vinculadas.",
    confirmLabel: "Excluir cadastro", tone: "danger", icon: "trash",
  });
  if (!agreed) return;
  busy.value = true;
  error.value = "";
  try {
    if (mode === "unit") {
      await api.delete(`/startup-simulation-units/${id}`);
      selectedUnitId.value = "";
      selectedProjectId.value = "";
      await loadScopes();
    } else {
      await api.delete(`/startup-simulation-projects/${id}`);
      selectedProjectId.value = "";
      await loadProjects();
    }
    notice.value = "Cadastro excluído do simulador.";
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "Não foi possível excluir o cadastro.";
  } finally {
    busy.value = false;
  }
}

function addEquipment(): void {
  const name = equipmentName.value.trim();
  if (!name || !canWrite.value || draftRows.value.length >= 500) return;
  draftRows.value.push({
    name,
    origin: equipmentOrigin.value.trim() || null,
    discipline: equipmentDiscipline.value.trim() || null,
    supplier: equipmentSupplier.value.trim() || null,
    area: equipmentArea.value.trim() || null,
    responsible: equipmentResponsible.value.trim() || null,
    startupAt: null,
    suppliesDays: null, legalDays: null, manufactureDays: null, preStartDays: null,
  });
  // Caso a busca ou o mês estejam filtrando, exibir imediatamente o novo equipamento.
  search.value = "";
  monthFilter.value = "";
  addEquipmentDialog.value = false;
  equipmentName.value = "";
  equipmentOrigin.value = "";
  equipmentDiscipline.value = "";
  equipmentSupplier.value = "";
  equipmentArea.value = "";
  equipmentResponsible.value = "";
}

type EquipmentTextField = "origin" | "discipline" | "name" | "supplier" | "area" | "responsible";
function editText(index: number, field: EquipmentTextField, value: string): void {
  const current = draftRows.value[index];
  if (!current || !canWrite.value) return;
  draftRows.value[index] = { ...current, [field]: field === "name" ? value : value || null };
}

function removeEquipment(index: number): void {
  if (!canWrite.value || !draftRows.value[index]) return;
  draftRows.value.splice(index, 1);
}


const scenarioOptions = computed(() => scenarios.value.map((item) => ({ id: item.id, label: item.name })));
const activeScenario = computed(() => scenarios.value.find((s) => s.id === activeId.value) ?? null);
const activePreview = computed(() => activeScenario.value
  ? previewScenario(activeScenario.value, draftName.value, draftStartup.value, draftRows.value) : null);
const comparisons = computed(() => {
  const selected = [leftId.value, rightId.value].filter((id, index, all) => id && all.indexOf(id) === index);
  return selected.map((id) => id === activeId.value ? activePreview.value : scenarios.value.find((s) => s.id === id))
    .filter((item): item is StartupScenario => Boolean(item));
});
const comparisonA = computed(() => comparisons.value.find(item => item.id === leftId.value) ?? null);
const comparisonB = computed(() => comparisons.value.find(item => item.id === rightId.value) ?? null);

const dirty = computed(() => {
  const source = activeScenario.value;
  if (!source) return false;
  return JSON.stringify({ name: draftName.value, startupAt: draftStartup.value, items: draftRows.value })
    !== JSON.stringify({ name: source.name, startupAt: source.startupAt, items: asDraftItems(source) });
});
const metricTitle = computed(() => ({
  negotiations: "Datas-limite de negociação por mês",
  contracts: "Datas-limite para contrato / OC por mês",
  deliveries: "Datas-limite de entrega por mês",
}[metric.value]));
const visibleEntries = computed(() => {
  const rows = activePreview.value?.items ?? [];
  const value = search.value.trim().toLocaleLowerCase("pt-BR");
  return rows.map((row, index) => ({ row, index })).filter(({ row }) => {
    if (value && ![row.name, row.origin, row.supplier, row.discipline, row.area, row.responsible]
      .some((part) => part?.toLocaleLowerCase("pt-BR").includes(value))) return false;
    if (monthFilter.value) {
      const key = {
        negotiations: row.negotiationDeadline,
        contracts: row.contractDeadline,
        deliveries: row.deliveryDeadline,
      }[metric.value];
      if (!key?.startsWith(monthFilter.value)) return false;
    }
    return true;
  });
});

/** Selecionar um prazo do cenário B troca a tabela editável para B, com proteção do rascunho. */
async function selectComparisonDeadline(
  scenarioId: string, selectedMetric: StartupMetric, selectedMonth: string,
): Promise<void> {
  if (busy.value || !scenarios.value.some(item => item.id === scenarioId)) return;
  if (scenarioId !== activeId.value) {
    if (!await discardBeforeSwitch()) return;
    selectActive(scenarioId);
  }
  metric.value = selectedMetric;
  monthFilter.value = selectedMonth;
  search.value = "";
  await nextTick();
  if (typeof document !== "undefined") {
    document.getElementById("startup-equipment-planning")?.scrollIntoView({
      behavior: "smooth", block: "start",
    });
  }
}

function selectActive(id: string): void {
  const source = scenarios.value.find((scenario) => scenario.id === id);
  activeId.value = source?.id ?? "";
  draftName.value = source?.name ?? "";
  draftStartup.value = source?.startupAt ?? "";
  draftRows.value = source ? asDraftItems(source) : [];
  monthFilter.value = "";
}

async function reload(): Promise<void> {
  const projectId = selectedProjectId.value;
  if (!canRead.value || !projectId) {
    scenarios.value = [];
    selectActive("");
    leftId.value = "";
    rightId.value = "";
    return;
  }
  loading.value = true;
  error.value = "";
  try {
    const result = await api.get<StartupScenarioList>("/startup-scenarios", {
      simulation_project_id: projectId,
    });
    if (projectId !== selectedProjectId.value) return;
    scenarios.value = result.items;
    if (!scenarios.value.some((s) => s.id === activeId.value)) selectActive(scenarios.value[0]?.id ?? "");
    if (!scenarios.value.some((s) => s.id === leftId.value)) leftId.value = scenarios.value[0]?.id ?? "";
    if (!scenarios.value.some((s) => s.id === rightId.value) || rightId.value === leftId.value) {
      rightId.value = scenarios.value.find((s) => s.id !== leftId.value)?.id ?? "";
    }
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "Não foi possível carregar os cenários.";
  } finally {
    loading.value = false;
  }
}

onMounted(async () => {
  if (!canRead.value) return;
  await loadScopes();
});

function editNumber(index: number, field: "suppliesDays" | "legalDays" | "manufactureDays" | "preStartDays", value: unknown) {
  const raw = String(value ?? "").trim();
  const number = raw === "" ? null : Number(raw);
  if (number !== null && (!Number.isInteger(number) || number < 0 || number > 36500)) return;
  const current = draftRows.value[index];
  if (!current) return;
  draftRows.value[index] = { ...current, [field]: number };
}
function editStartup(index: number, value: string) {
  const current = draftRows.value[index];
  if (current) draftRows.value[index] = { ...current, startupAt: value || null };
}

async function save(): Promise<void> {
  if (!activeScenario.value || !canWrite.value || !dirty.value) return;
  if (!draftName.value.trim() || !/^\d{4}-\d{2}-\d{2}$/.test(draftStartup.value)) {
    error.value = "Informe um nome e uma data de startup válidos.";
    return;
  }
  if (draftRows.value.some(row => !row.name.trim())) {
    error.value = "Preencha o nome de todos os equipamentos antes de salvar o cenário.";
    return;
  }
  busy.value = true;
  error.value = "";
  try {
    const id = activeScenario.value.id;
    await api.put(`/startup-scenarios/${id}`, {
      name: draftName.value.trim(), startupAt: draftStartup.value, items: draftRows.value,
    });
    await reload();
    selectActive(id);
    notice.value = "Cenário salvo. Prazos e indicadores recalculados.";
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "Não foi possível salvar o cenário.";
  } finally {
    busy.value = false;
  }
}

function openCreate(clone: boolean): void {
  if (!selectedProjectId.value) return;
  creatingClone.value = clone;
  newName.value = clone && activeScenario.value ? `${activeScenario.value.name} (cópia)` : "";
  newStartup.value = clone && activeScenario.value ? activeScenario.value.startupAt : "";
  createDialog.value = true;
}
async function create(): Promise<void> {
  if (!newName.value.trim() || !/^\d{4}-\d{2}-\d{2}$/.test(newStartup.value)) {
    error.value = "Informe o nome e a data de startup do novo cenário.";
    return;
  }
  busy.value = true;
  error.value = "";
  try {
    let result: StartupScenario;
    if (creatingClone.value && activeScenario.value) {
      result = await api.post<StartupScenario>(`/startup-scenarios/${activeScenario.value.id}/clone`, {
        name: newName.value.trim(), startupAt: newStartup.value,
      });
    } else {
      result = await api.post<StartupScenario>("/startup-scenarios", {
        simulationProjectId: selectedProjectId.value, name: newName.value.trim(),
        startupAt: newStartup.value, source: "MANUAL", items: [],
      });
    }
    createDialog.value = false;
    await reload();
    selectActive(result.id);
    if (!leftId.value) leftId.value = result.id;
    else if (!rightId.value && leftId.value !== result.id) rightId.value = result.id;
    notice.value = "Cenário criado. Ajuste os prazos e salve quando necessário.";
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "Erro ao criar cenário.";
  } finally {
    busy.value = false;
  }
}

async function remove(): Promise<void> {
  const scenario = activeScenario.value;
  if (!scenario || !canWrite.value) return;
  const approved = await confirm.confirm({
    title: "Excluir simulação",
    message: `Excluir o cenário "${scenario.name}"?`,
    detail: "Esta ação exclui somente a simulação. Não altera equipamentos ou processos oficiais.",
    confirmLabel: "Excluir cenário", tone: "danger", icon: "trash",
  });
  if (!approved) return;
  busy.value = true;
  try {
    await api.delete(`/startup-scenarios/${scenario.id}`);
    selectActive("");
    await reload();
    notice.value = "Cenário excluído.";
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "Não foi possível excluir.";
  } finally {
    busy.value = false;
  }
}

async function importExcel(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = "";
  if (!file || !canWrite.value || !selectedProjectId.value) return;
  busy.value = true;
  error.value = "";
  notice.value = "";
  importWarnings.value = [];
  try {
    const parsed = await readStartupWorkbook(file);
    importWarnings.value = parsed.warnings;
    const created: string[] = [];
    for (const scenario of parsed.scenarios) {
      const result = await api.post<StartupScenario>("/startup-scenarios", {
        simulationProjectId: selectedProjectId.value,
        name: scenario.name, startupAt: scenario.startupAt, source: "EXCEL",
        items: scenario.items,
      });
      created.push(result.id);
    }
    await reload();
    if (created[0]) {
      leftId.value = created[0];
      selectActive(created[0]);
    }
    if (created[1]) rightId.value = created[1];
    notice.value = `${created.length} cenário(s) importado(s), com ${parsed.scenarios.reduce((sum, s) => sum + s.items.length, 0)} linhas.`;
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "Não foi possível importar a planilha.";
  } finally {
    busy.value = false;
  }
}

async function exportExcel(): Promise<void> {
  busy.value = true;
  error.value = "";
  try {
    await exportStartupScenarios(comparisons.value.length ? comparisons.value : (activePreview.value ? [activePreview.value] : []));
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "Erro ao exportar os resultados.";
  } finally {
    busy.value = false;
  }
}

</script>

<template>
  <ModuleWorkspace
    eyebrow="Planejamento · Equipamentos"
    title="Simulador de Startup"
    description="Simule prazos de negociação, contrato/OC e entrega a partir do startup, sem alterar o planejamento oficial."
  >
    <SimulationScopeFilters
      v-if="canRead"
      :units="units" :projects="projects"
      :unit-id="selectedUnitId" :project-id="selectedProjectId"
      :loading="scopesLoading || busy" :can-write="canWrite"
      @select-unit="chooseUnit" @select-project="chooseProject"
      @create-unit="openScopeDialog('unit')" @create-project="openScopeDialog('project')"
      @delete-unit="deleteScope('unit')" @delete-project="deleteScope('project')"
    />
    <div v-if="!canRead" class="surface simulation-empty">Seu perfil não possui acesso aos equipamentos.</div>
    <template v-else>
      <VAlert v-if="error" type="error" class="mb-3" role="alert">{{ error }}</VAlert>
      <VAlert v-if="notice" type="success" class="mb-3" closable @click:close="notice = ''">{{ notice }}</VAlert>
      <VAlert v-if="importWarnings.length" type="warning" class="mb-3" closable @click:close="importWarnings = []">
        {{ importWarnings.length }} aviso(s) na importação. {{ importWarnings.slice(0, 3).join(" · ") }}
      </VAlert>
      <VProgressLinear v-if="busy" color="primary" indeterminate class="mb-2" aria-label="Processando simulação" />

      <section class="surface simulation-toolbar" aria-label="Ações dos cenários">
        <div class="toolbar-text">
          <h2>Cenários de planejamento</h2>
          <p>Defina o startup e os prazos por equipamento. Datas calculadas seguem a planilha: entrega = startup − antecedência; contrato = entrega − fabricação; negociação = contrato − Jurídico.</p>
        </div>
        <div class="toolbar-actions">
          <VBtn v-if="canWrite" color="primary" :prepend-icon="mdiPlus" :disabled="!selectedProjectId || busy" @click="openCreate(false)">Novo cenário</VBtn>
          <VBtn v-if="canWrite" :prepend-icon="mdiContentCopy" :disabled="!activeScenario || busy" @click="openCreate(true)">Duplicar</VBtn>
          <VBtn v-if="canWrite" :prepend-icon="mdiFileExcelOutline" :disabled="!selectedProjectId || busy" @click="fileInput?.click()">Importar Excel</VBtn>
          <VBtn :prepend-icon="mdiFileExcelOutline" :disabled="!activePreview || busy" @click="exportExcel">Exportar Excel</VBtn>
          <input ref="fileInput" type="file" accept=".xlsx" class="sr-only" tabindex="-1" @change="importExcel" />
        </div>
      </section>

      <div v-if="!selectedProjectId" class="surface simulation-empty">
        <h2>{{ units.length ? "Crie ou selecione uma obra" : "Cadastre sua primeira unidade" }}</h2>
        <p>Use os cadastros exclusivos acima para organizar suas simulações de startup, sem depender de unidades e obras operacionais do Hub.</p>
      </div>
      <div v-else-if="loading" class="simulation-loading" role="status" aria-busy="true">
        <div v-for="index in 4" :key="index" class="surface simulation-skeleton"><CardProgress /><SkeletonBlock :lines="3" /></div>
      </div>
      <div v-else-if="!scenarios.length" class="surface simulation-empty">
        <h2>Nenhum cenário cadastrado nesta obra</h2>
        <p>Importe os cenários da planilha Excel ou crie uma simulação vazia e adicione seus equipamentos.</p>
      </div>

      <template v-else>
        <section class="simulation-selectors">
          <div class="surface simulation-selector">
            <FloatingFilterSelect
              :model-value="activeId" :options="scenarioOptions" label="Cenário em edição" :clearable="false"
              @change="chooseScenario"
            />
          </div>
          <div class="surface simulation-selector">
            <FloatingFilterSelect v-model="leftId" :options="scenarioOptions" label="Comparar · cenário A" :clearable="false" />
          </div>
          <div class="surface simulation-selector">
            <FloatingFilterSelect v-model="rightId" :options="scenarioOptions" label="Comparar · cenário B" clearable />
          </div>
        </section>

        <StartupComparisonSummary
          v-if="activePreview"
          :scenario-a="comparisonA"
          :scenario-b="comparisonB"
          :draft-scenario-id="dirty ? activeId : null"
        />

        <DashboardChartFrame
          v-if="activePreview" :title="metricTitle"
          subtitle="Quantidade de equipamentos com prazo-limite em cada mês. Clique em um ponto para filtrar a tabela."
          :empty="!comparisons.length || comparisons.every((s) => !s.summary.monthly.length)"
        >
          <template #actions>
            <NavigationMenu
              v-model="metric"
              class="metric-navigation"
              :items="metricNavigationItems"
              aria-label="Selecionar tipo de prazo exibido no gráfico"
            />
          </template>
          <StartupMonthlyChart :scenarios="comparisons" :metric="metric" @select-month="monthFilter = $event" />
        </DashboardChartFrame>

        <StartupMonthlyComparisonTable
          v-if="activePreview"
          :scenario-a="comparisonA"
          :scenario-b="comparisonB"
          :active-scenario-id="activeId"
          :active-metric="metric"
          :active-month="monthFilter"
          @select-deadline="selectComparisonDeadline"
        />

        <section v-if="activePreview" class="surface simulation-editor">
          <div class="editor-heading">
            <div>
              <h2>Parâmetros do cenário</h2>
              <p>Os ajustes aparecem imediatamente nos resultados. Salve para persistir no banco.</p>
            </div>
            <div class="editor-actions">
              <VBtn v-if="canWrite" color="error" variant="text" :prepend-icon="mdiDeleteOutline" :disabled="busy" @click="remove">Excluir</VBtn>
              <VBtn v-if="canWrite" color="primary" :prepend-icon="mdiContentSave" :disabled="busy || !dirty" :loading="busy" @click="save">Salvar alterações</VBtn>
            </div>
          </div>
          <div class="editor-fields">
            <VTextField v-model="draftName" label="Nome do cenário" :readonly="!canWrite" maxlength="120" />
            <VTextField v-model="draftStartup" type="date" label="Data de startup" :readonly="!canWrite" />
            <div class="source-hint">Origem: {{ activeScenario?.source === "EXCEL" ? "Planilha Excel" : activeScenario?.source === "PROJECT" ? "Legado migrado" : "Simulação manual" }}</div>
          </div>
        </section>

        <section id="startup-equipment-planning" v-if="activePreview" class="surface simulation-table-section">
          <header class="table-heading">
            <div>
              <h2>Planejamento por equipamento</h2>
              <p>{{ visibleEntries.length }} de {{ activePreview.items.length }} equipamentos exibidos · prazos em dias corridos</p>
            </div>
            <div class="editor-actions">
              <VBtn v-if="monthFilter" variant="tonal" color="primary" size="small" @click="monthFilter = ''">Limpar mês {{ monthFilter }}</VBtn>
              <VBtn v-if="canWrite" color="primary" :prepend-icon="mdiPlus" size="small"  :disabled="busy || draftRows.length >= 500" @click="addEquipmentDialog = true">Adicionar equipamento</VBtn>
            </div>
          </header>
          <div class="table-search">
            <FloatingFilterInput v-model="search" label="Buscar equipamento, fornecedor ou disciplina" placeholder="Pesquisar nesta simulação" />
          </div>
          <StartupEquipmentTable
            :entries="visibleEntries" :editable="canWrite" :loading="busy"
            @edit-text="editText" @edit-number="editNumber"
            @edit-startup="editStartup" @remove="removeEquipment"
          />
          <p class="simulation-footnote">
            Célula “Startup próprio” vazia herda o startup do cenário. Suprimentos é informativo e não entra nas três fórmulas da planilha.
            Resultados sem parâmetros suficientes aparecem como “—”. A busca e o filtro de mês afetam apenas a tabela, não os totais do cenário.
          </p>
        </section>
      </template>

      <VDialog :model-value="Boolean(scopeDialog)" max-width="490" persistent @update:model-value="!$event && (scopeDialog = '')">
        <VCard>
          <VCardTitle>{{ scopeDialog === 'unit' ? "Nova unidade do simulador" : "Nova obra do simulador" }}</VCardTitle>
          <VCardText>
            <VTextField
              v-model="scopeName"
              :label="scopeDialog === 'unit' ? 'Nome da unidade' : 'Nome da obra'"
              maxlength="160"
              autofocus
              @keyup.enter="createScope"
            />
            <p class="dialog-hint">Este cadastro pertence exclusivamente ao Simulador de Startup.</p>
          </VCardText>
          <VCardActions>
            <VBtn :disabled="busy" @click="scopeDialog = ''">Cancelar</VBtn>
            <VBtn color="primary" :disabled="!scopeName.trim() || busy" :loading="busy" @click="createScope">Cadastrar</VBtn>
          </VCardActions>
        </VCard>
      </VDialog>

      <VDialog v-model="addEquipmentDialog" max-width="540" persistent scrollable>
        <VCard>
          <VCardTitle>Adicionar equipamento ao cenário</VCardTitle>
          <VCardText>
            <p class="dialog-hint mb-3">Preencha os mesmos campos da planilha. Somente o nome é obrigatório; todos os demais podem ser informados ou alterados na tabela.</p>
            <VCombobox
              v-model="equipmentOrigin"
              :items="['Nacional', 'Importado']"
              label="Origem"
              maxlength="160"
              class="mb-3"
              hint="Escolha uma opção ou digite outra origem."
              persistent-hint
            />
            <VTextField v-model="equipmentDiscipline" label="Disciplina" maxlength="160" class="mb-3" />
            <VTextField v-model="equipmentName" label="Nome do equipamento *" maxlength="500" class="mb-3" autofocus />
            <VTextField v-model="equipmentSupplier" label="Fornecedor" maxlength="200" class="mb-3" />
            <VTextField v-model="equipmentArea" label="Área" maxlength="160" class="mb-3" />
            <VTextField v-model="equipmentResponsible" label="Responsável" maxlength="160" />
            <p class="dialog-hint mt-3">Os lead times e a data de startup são preenchidos na tabela. Limites de negociação, contrato/OC e entrega são sempre calculados automaticamente.</p>
          </VCardText>
          <VCardActions>
            <VBtn @click="addEquipmentDialog = false">Cancelar</VBtn>
            <VBtn color="primary" :disabled="!equipmentName.trim() || draftRows.length >= 500" @click="addEquipment">Adicionar à tabela</VBtn>
          </VCardActions>
        </VCard>
      </VDialog>

      <VDialog v-model="createDialog" max-width="490" persistent>
        <VCard>
          <VCardTitle>{{ creatingClone ? "Duplicar cenário" : "Novo cenário" }}</VCardTitle>
          <VCardText>
            <VTextField v-model="newName" label="Nome do cenário" maxlength="120" class="mb-4" autofocus />
            <VTextField v-model="newStartup" type="date" label="Data de startup" />
            <p class="dialog-hint">{{ creatingClone ? "Todos os equipamentos e prazos serão copiados. A data geral do startup será a nova referência." : "Cria um cenário vazio nesta obra. Use “Adicionar equipamento” ou importe o Excel para preencher o planejamento." }}</p>
          </VCardText>
          <VCardActions>
            <VBtn :disabled="busy" @click="createDialog = false">Cancelar</VBtn>
            <VBtn color="primary" :loading="busy" :disabled="!newName.trim() || !newStartup" @click="create">{{ creatingClone ? "Duplicar" : "Criar cenário" }}</VBtn>
          </VCardActions>
        </VCard>
      </VDialog>
    </template>
  </ModuleWorkspace>
</template>

<style scoped>
.simulation-toolbar { display: flex; justify-content: space-between; align-items: center; gap: 24px; flex-wrap: wrap; padding: 18px; margin-bottom: 16px; }
.toolbar-text { flex: 1 1 360px; }
.toolbar-text h2, .editor-heading h2, .table-heading h2 { margin: 0; font-size: 15px; font-weight: 800; color: #213758; }
.toolbar-text p, .editor-heading p, .table-heading p { margin: 5px 0 0; color: #7d8a9d; font-size: 11.5px; line-height: 1.6; max-width: 860px; }
.toolbar-actions, .editor-actions { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
.simulation-empty { text-align: center; padding: 65px 24px; color: #7d8a9d; margin-bottom: 15px; }
.simulation-empty h2 { font-size: 17px; font-weight: 800; color: #304f7e; }
.simulation-empty p { font-size: 12px; margin-top: 5px; }
.simulation-loading { display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 14px; }
.simulation-skeleton { padding: 20px; position: relative; overflow: hidden; }
.simulation-selectors { display: grid; grid-template-columns: repeat(3,minmax(0,1fr)); gap: 14px; margin-bottom: 16px; }
.simulation-selector { padding: 15px 15px 5px; }
.simulation-editor { padding: 18px; margin-bottom: 16px; }
.editor-heading, .table-heading { display: flex; justify-content: space-between; align-items: start; flex-wrap: wrap; gap: 14px; margin-bottom: 16px; }
.editor-fields { display: grid; grid-template-columns: minmax(0,2fr) minmax(180px,1fr) auto; align-items: center; gap: 12px; }
.source-hint { font-size: 11px; color: #8190a3; }
.simulation-table-section { padding: 18px; margin-top: 16px; }
.table-search { max-width: 430px; margin-bottom: 12px; }
.simulation-footnote { margin: 12px 0 0; font-size: 10.5px; line-height: 1.6; color: #8896a8; }
.dialog-hint { font-size: 11.5px; line-height: 1.55; color: #8793a4; }
.metric-navigation { width: fit-content !important; flex: 0 0 auto; flex-wrap: nowrap; align-self: flex-start; margin-left: auto; padding: 4px; }
.metric-navigation :deep(.analysis-nav__item) { padding: 7px 11px; font-size: 12px; }
.metric-navigation :deep(.analysis-nav__icon) { width: 14px; height: 14px; }
@media(max-width:1100px) { .simulation-selectors { grid-template-columns: repeat(2,minmax(0,1fr)); } .editor-fields { grid-template-columns: 1fr 1fr; } }
@media(max-width:700px) { .simulation-selectors, .simulation-loading, .editor-fields { grid-template-columns: minmax(0,1fr); } .simulation-toolbar, .simulation-editor, .simulation-table-section { padding: 14px; } .metric-navigation { width: 100% !important; flex-wrap: wrap; } }
</style>
