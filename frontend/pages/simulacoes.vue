<script setup lang="ts">
import { VAlert, VBtn, VBtnToggle, VCard, VCardActions, VCardText, VCardTitle, VDialog, VProgressLinear, VTextField } from "vuetify/components";
import { mdiContentCopy, mdiContentSave, mdiDeleteOutline, mdiFileExcelOutline, mdiPlus } from "@mdi/js";
import type { StartupItemInput, StartupMetric, StartupScenario, StartupScenarioList } from "~/types/startupSimulation";
import { asDraftItems, formatScenarioDate, previewScenario } from "~/utils/startupSimulation";
import { readStartupWorkbook } from "~/utils/startupWorkbook";
import { exportStartupScenarios } from "~/utils/startupExport";

definePageMeta({ middleware: "auth" });

const api = useApi();
const route = useRoute();
const auth = useAuthStore();
const context = useModuleContextStore();
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
const search = ref("");
const monthFilter = ref("");
const fileInput = ref<HTMLInputElement | null>(null);
const createDialog = ref(false);
const creatingClone = ref(false);
const newName = ref("");
const newStartup = ref("");

const scenarioOptions = computed(() => scenarios.value.map((item) => ({ id: item.id, label: item.name })));
const activeScenario = computed(() => scenarios.value.find((s) => s.id === activeId.value) ?? null);
const activePreview = computed(() => activeScenario.value
  ? previewScenario(activeScenario.value, draftName.value, draftStartup.value, draftRows.value) : null);
const comparisons = computed(() => {
  const selected = [leftId.value, rightId.value].filter((id, index, all) => id && all.indexOf(id) === index);
  return selected.map((id) => id === activeId.value ? activePreview.value : scenarios.value.find((s) => s.id === id))
    .filter((item): item is StartupScenario => Boolean(item));
});
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
    if (value && ![row.name, row.supplier, row.discipline, row.area, row.responsible]
      .some((part) => part?.toLocaleLowerCase("pt-BR").includes(value))) return false;
    if (context.selectedEquipment && row.equipmentId !== context.selectedEquipment) return false;
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

function selectActive(id: string): void {
  const source = scenarios.value.find((scenario) => scenario.id === id);
  activeId.value = source?.id ?? "";
  draftName.value = source?.name ?? "";
  draftStartup.value = source?.startupAt ?? "";
  draftRows.value = source ? asDraftItems(source) : [];
  monthFilter.value = "";
}

async function reload(): Promise<void> {
  const projectContextId = context.selectedProjectContext;
  if (!canRead.value || !projectContextId) {
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
      project_context_id: projectContextId,
    });
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
  await context.initialize({
    unit: typeof route.query.unit === "string" ? route.query.unit : undefined,
    project: typeof route.query.project === "string" ? route.query.project : undefined,
    equipment: typeof route.query.equipment === "string" ? route.query.equipment : undefined,
  });
  await reload();
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
  if (!context.selectedProjectContext) return;
  creatingClone.value = clone;
  newName.value = clone && activeScenario.value ? `${activeScenario.value.name} (cópia)` : "";
  newStartup.value = clone && activeScenario.value ? activeScenario.value.startupAt
    : context.equipmentOptions.find((item) => item.startupAt)?.startupAt?.slice(0, 10) ?? "";
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
        projectContextId: context.selectedProjectContext, name: newName.value.trim(),
        startupAt: newStartup.value, source: "PROJECT",
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
  if (!file || !canWrite.value || !context.selectedProjectContext) return;
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
        projectContextId: context.selectedProjectContext,
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

function dateAverage(value: number | null): string {
  return value === null ? "—" : `${value.toLocaleString("pt-BR", { maximumFractionDigits: 2 })} dias`;
}
</script>

<template>
  <ModuleWorkspace
    eyebrow="Planejamento · Equipamentos"
    title="Simulador de Startup"
    description="Simule prazos de negociação, contrato/OC e entrega a partir do startup, sem alterar o planejamento oficial."
  >
    <ModuleFilters show-project-context :refreshing="loading" @change="reload" @refresh="reload" />
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
          <VBtn v-if="canWrite" color="primary" :prepend-icon="mdiPlus" :disabled="!context.selectedProjectContext || busy" @click="openCreate(false)">Novo cenário</VBtn>
          <VBtn v-if="canWrite" :prepend-icon="mdiContentCopy" :disabled="!activeScenario || busy" @click="openCreate(true)">Duplicar</VBtn>
          <VBtn v-if="canWrite" :prepend-icon="mdiFileExcelOutline" :disabled="!context.selectedProjectContext || busy" @click="fileInput?.click()">Importar Excel</VBtn>
          <VBtn :prepend-icon="mdiFileExcelOutline" :disabled="!activePreview || busy" @click="exportExcel">Exportar Excel</VBtn>
          <input ref="fileInput" type="file" accept=".xlsx" class="sr-only" tabindex="-1" @change="importExcel" />
        </div>
      </section>

      <div v-if="!context.selectedProjectContext" class="surface simulation-empty">
        <h2>Selecione uma obra</h2>
        <p>Escolha uma unidade e uma obra nos filtros acima para acessar as simulações correspondentes.</p>
      </div>
      <div v-else-if="loading" class="simulation-loading" role="status" aria-busy="true">
        <div v-for="index in 4" :key="index" class="surface simulation-skeleton"><CardProgress /><SkeletonBlock :lines="3" /></div>
      </div>
      <div v-else-if="!scenarios.length" class="surface simulation-empty">
        <h2>Nenhum cenário cadastrado nesta obra</h2>
        <p>Importe as abas da planilha LEM F2 ou crie um cenário a partir dos equipamentos cadastrados no Hub.</p>
      </div>

      <template v-else>
        <section class="simulation-selectors">
          <div class="surface simulation-selector">
            <FloatingFilterSelect
              :model-value="activeId" :options="scenarioOptions" label="Cenário em edição" :clearable="false"
              @change="selectActive"
            />
          </div>
          <div class="surface simulation-selector">
            <FloatingFilterSelect v-model="leftId" :options="scenarioOptions" label="Comparar · cenário A" :clearable="false" />
          </div>
          <div class="surface simulation-selector">
            <FloatingFilterSelect v-model="rightId" :options="scenarioOptions" label="Comparar · cenário B" clearable />
          </div>
        </section>

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
            <div class="source-hint">Origem: {{ activeScenario?.source === "EXCEL" ? "Planilha Excel" : activeScenario?.source === "PROJECT" ? "Cadastro do Hub" : "Cenário duplicado" }}</div>
          </div>
        </section>

        <div v-if="activePreview" class="simulation-kpis">
          <MetricCard label="Equipamentos" :value="String(activePreview.summary.equipments)" :detail="`${activePreview.summary.negotiationsCalculated} com negociação calculada`" />
          <MetricCard label="Primeira negociação" :value="formatScenarioDate(activePreview.summary.firstNegotiation)" detail="Data-limite inicial" />
          <MetricCard label="Última negociação" :value="formatScenarioDate(activePreview.summary.lastNegotiation)" detail="Data-limite final" />
          <MetricCard label="Primeira entrega" :value="formatScenarioDate(activePreview.summary.firstDelivery)" detail="Na obra" />
          <MetricCard label="Fabricação média" :value="dateAverage(activePreview.summary.averageManufactureDays)" detail="Dos prazos informados" />
          <MetricCard label="Antecedência média" :value="dateAverage(activePreview.summary.averagePreStartDays)" detail="Dias antes do startup" />
        </div>

        <DashboardChartFrame
          v-if="activePreview" :title="metricTitle"
          subtitle="Quantidade de equipamentos com prazo-limite em cada mês. Clique em um ponto para filtrar a tabela."
          :empty="!comparisons.length || comparisons.every((s) => !s.summary.monthly.length)"
        >
          <template #actions>
            <VBtnToggle v-model="metric" color="primary" mandatory density="compact" variant="outlined" divided>
              <VBtn value="negotiations" size="small">Negociação</VBtn>
              <VBtn value="contracts" size="small">Contrato/OC</VBtn>
              <VBtn value="deliveries" size="small">Entrega</VBtn>
            </VBtnToggle>
          </template>
          <StartupMonthlyChart :scenarios="comparisons" :metric="metric" @select-month="monthFilter = $event" />
        </DashboardChartFrame>

        <section v-if="activePreview" class="surface simulation-table-section">
          <header class="table-heading">
            <div>
              <h2>Planejamento por equipamento</h2>
              <p>{{ visibleEntries.length }} de {{ activePreview.items.length }} equipamentos exibidos · prazos em dias corridos</p>
            </div>
            <VBtn v-if="monthFilter" variant="tonal" color="primary" size="small" @click="monthFilter = ''">Limpar mês {{ monthFilter }}</VBtn>
          </header>
          <div class="table-search">
            <FloatingFilterInput v-model="search" label="Buscar equipamento, fornecedor ou disciplina" placeholder="Pesquisar nesta simulação" />
          </div>
          <StartupEquipmentTable
            :entries="visibleEntries" :editable="canWrite" :loading="busy"
            @edit-number="editNumber" @edit-startup="editStartup"
          />
          <p class="simulation-footnote">
            Célula “Startup próprio” vazia herda o startup do cenário. Suprimentos é informativo e não entra nas três fórmulas da planilha.
            Resultados sem parâmetros suficientes aparecem como “—”. O filtro de equipamento afeta a tabela, não os totais do cenário.
          </p>
        </section>
      </template>

      <VDialog v-model="createDialog" max-width="490" persistent>
        <VCard>
          <VCardTitle>{{ creatingClone ? "Duplicar cenário" : "Novo cenário" }}</VCardTitle>
          <VCardText>
            <VTextField v-model="newName" label="Nome do cenário" maxlength="120" class="mb-4" autofocus />
            <VTextField v-model="newStartup" type="date" label="Data de startup" />
            <p class="dialog-hint">{{ creatingClone ? "Todos os equipamentos e prazos serão copiados. A data geral do startup será a nova referência." : "Cria um snapshot dos equipamentos da obra, com prazos conhecidos do Hub e 20 dias iniciais de Jurídico, editáveis." }}</p>
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
.simulation-kpis { display: grid; grid-template-columns: repeat(3,minmax(0,1fr)); gap: 14px; margin-bottom: 16px; }
.simulation-kpis :deep(.metric-card) { padding: 17px 19px; background: #fff; border: 1px solid #e7ecf3; border-radius: 12px; box-shadow: 0 2px 9px rgba(36,60,95,.035); }
.simulation-kpis :deep(.label) { color: #8390a3; font-size: 11px; }
.simulation-kpis :deep(.value) { color: #213758; font-size: 23px; font-weight: 800; margin-top: 5px; }
.simulation-kpis :deep(.detail) { color: #9aa6b5; font-size: 10.5px; margin-top: 4px; }
.simulation-table-section { padding: 18px; margin-top: 16px; }
.table-search { max-width: 430px; margin-bottom: 12px; }
.simulation-footnote { margin: 12px 0 0; font-size: 10.5px; line-height: 1.6; color: #8896a8; }
.dialog-hint { font-size: 11.5px; line-height: 1.55; color: #8793a4; }
@media(max-width:1100px) { .simulation-selectors, .simulation-kpis { grid-template-columns: repeat(2,minmax(0,1fr)); } .editor-fields { grid-template-columns: 1fr 1fr; } }
@media(max-width:700px) { .simulation-selectors, .simulation-kpis, .simulation-loading, .editor-fields { grid-template-columns: minmax(0,1fr); } .simulation-toolbar, .simulation-editor, .simulation-table-section { padding: 14px; } }
</style>
