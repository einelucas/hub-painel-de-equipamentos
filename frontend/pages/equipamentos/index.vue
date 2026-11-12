<script setup lang="ts">
import {
  mdiAccount,
  mdiCloudDownloadOutline,
  mdiLayers,
  mdiMapMarker,
  mdiPackageVariant,
  mdiPlus,
  mdiTag,
  mdiTuneVariant,
} from "@mdi/js";
import type {
  CatalogItem,
  CatalogList,
  Equipment,
  EquipmentList,
  Pagination,
  Responsible,
} from "~/types/equipment";
import { loadEapLocationOptions } from "~/utils/eapLocationOptions";
import FloatingFilterSelect from "~/components/ui/FloatingFilterSelect.vue";
import EquipmentExecutiveReport from "~/components/equipment/EquipmentExecutiveReport.vue";
import { Sparkles } from "lucide-vue-next";
import { VBtn, VCard, VCardActions, VCardText, VCardTitle, VCheckbox, VDialog, VSpacer } from "vuetify/components";
import type { SearchableOption } from "~/types/ui";
import { STAGE_OPTIONS, toOptions } from "~/utils/selectOptions";
import { collectAllPages } from "~/utils/pagination";
import type { RealtimeChangeEvent } from "~/composables/useRealtimeSync";

definePageMeta({ middleware: "auth" });
const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const api = useApi();
const context = useModuleContextStore();

const equipments = ref<Equipment[]>([]);
const pagination = ref<Pagination | null>(null);
const disciplines = ref<CatalogItem[]>([]);
const responsibles = ref<Responsible[]>([]);
const areas = ref<CatalogItem[]>([]);
const workPackages = ref<CatalogItem[]>([]);
const criticalityLabels = ref<CatalogItem[]>([]);
const editingTable = ref(false);
const editorProjectContextId = ref("");
const editorUnitId = ref("");
const bulkEditorRef = ref<{ hasPending: () => boolean; confirmDiscard: () => boolean } | null>(null);
const stage = ref<string>("");
const disciplineId = ref("");
const responsibleUserId = ref("");
const areaId = ref("");
const workPackageId = ref("");
const exporting = ref(false);
const exportProgress = ref("");
const page = ref(1);
const loading = ref(true);
const refreshing = ref(false);
const error = ref("");
const showForm = ref(false);
const showAdmin = ref(false);
const reportSelection = ref<{
  unitId: string;
  projectContextId: string;
  projectContextIds: string[];
  unitName: string;
  projectName: string;
} | null>(null);
const showReportPicker = ref(false);
const selectedReportProjectIds = ref<string[]>([]);
let requestVersion = 0;
let quietRefresh = false;
let unsubscribeSync: (() => void) | null = null;
const realtime = useRealtimeSync();

const allowed = computed(() => auth.can("equipments:read"));
const canEditTable = computed(() => auth.can("equipments:write") && Boolean(context.selectedProjectContext));
const canCreate = computed(
  () => auth.can("equipments:write") && Boolean(context.selectedUnit),
);
// Administração contextual: só aparece para quem realmente pode administrar.
const canAdminister = computed(
  () => auth.can("catalogs:manage") || auth.can("users:manage"),
);
const availableReportProjects = computed(() =>
  context.projectContexts.filter((project) => project.active !== false),
);
const canGenerateReport = computed(
  () => Boolean(context.selectedUnit && availableReportProjects.value.length) &&
    !context.loading && !context.optionsLoading,
);

/** A escolha das obras é independente dos filtros de equipamento e da tabela.
 * Um único contexto dispensa a seleção; vários exigem confirmação explícita. */
function openExecutiveReport(): void {
  if (!canGenerateReport.value) return;
  const projects = availableReportProjects.value;
  if (projects.length === 1) {
    confirmExecutiveReport([projects[0]!.id]);
    return;
  }
  selectedReportProjectIds.value =
    context.selectedProjectContext && projects.some((item) => item.id === context.selectedProjectContext)
      ? [context.selectedProjectContext]
      : projects.map((item) => item.id);
  showReportPicker.value = true;
}

function toggleReportProject(id: string, selected: boolean): void {
  selectedReportProjectIds.value = selected
    ? [...new Set([...selectedReportProjectIds.value, id])]
    : selectedReportProjectIds.value.filter((value) => value !== id);
}

function confirmExecutiveReport(ids: string[] = selectedReportProjectIds.value): void {
  const unit = context.units.find((item) => item.id === context.selectedUnit);
  const selected = availableReportProjects.value.filter((item) => ids.includes(item.id));
  if (!unit || selected.length === 0 || selected.length !== new Set(ids).size) {
    error.value = "As obras selecionadas não estão disponíveis nesta unidade. Atualize os filtros.";
    return;
  }
  showReportPicker.value = false;
  reportSelection.value = {
    unitId: unit.id,
    projectContextId: selected[0]!.id,
    projectContextIds: selected.map((item) => item.id),
    unitName: unit.name,
    projectName: selected.map((item) => item.name).join(" · "),
  };
}

/**
 * Área vem da EAP (Processo/Área), a mesma localização gravada no equipamento;
 * Work Package é um catálogo corporativo global (e nunca usa o `workPackage`
 * singular legado). Uma seleção que deixou de existir na nova lista é limpa;
 * uma que continua válida (ex.: catálogo administrado) permanece.
 */
async function loadAreaAndWorkPackageOptions(): Promise<void> {
  areas.value = await loadEapLocationOptions(api);
  workPackages.value = (
    await api.get<CatalogList<CatalogItem>>("/work-packages")
  ).items;
  if (!areas.value.some((item) => item.id === areaId.value)) areaId.value = "";
  if (!workPackages.value.some((item) => item.id === workPackageId.value))
    workPackageId.value = "";
}

/** Catálogos mudaram: recarrega o que a tela usa para refletir na hora. */
async function adminChanged(): Promise<void> {
  disciplines.value = (
    await api.get<CatalogList<CatalogItem>>("/disciplines")
  ).items;
  criticalityLabels.value = (
    await api.get<CatalogList<CatalogItem>>("/criticality-labels")
  ).items;
  await context.loadProjectContexts();
  await context.loadEquipmentOptions();
  if (context.selectedUnit) {
    responsibles.value = (
      await api.get<CatalogList<Responsible>>("/responsibles", {
        unit_id: context.selectedUnit,
      })
    ).items;
  }
  await loadAreaAndWorkPackageOptions();
  await load();
}

async function syncQuery(): Promise<void> {
  const query: Record<string, string> = {
    ...(route.query as Record<string, string>),
  };
  if (context.selectedUnit) query.unit = context.selectedUnit;
  else delete query.unit;
  if (context.selectedProjectContext)
    query.project = context.selectedProjectContext;
  else delete query.project;
  if (context.selectedEquipment) query.equipment = context.selectedEquipment;
  else delete query.equipment;
  await router.replace({ query });
}

/** Troca de página pela paginação controlada do Hub. */
function toggleTableEditing(): void {
  if (editingTable.value) {
    if (bulkEditorRef.value?.hasPending() && !bulkEditorRef.value.confirmDiscard()) return;
    editingTable.value = false;
    return;
  }
  if (!canEditTable.value) return;
  editorProjectContextId.value = context.selectedProjectContext;
  editorUnitId.value = context.selectedUnit;
  editingTable.value = true;
}

function editorSaved(): void {
  void load();
}

function onPageChange(next: number): void {
  page.value = next;
  void load();
}

async function load(): Promise<void> {
  const version = ++requestVersion;
  const quiet = quietRefresh;
  quietRefresh = false;
  if (!quiet) refreshing.value = true;
  error.value = "";
  try {
    const query: Record<string, unknown> = {
      ...context.apiQuery,
      page: page.value,
      pageSize: 25,
      sortBy: "name",
    };
    if (stage.value !== "") query.stage = Number(stage.value);
    if (disciplineId.value) query.discipline_id = disciplineId.value;
    if (responsibleUserId.value)
      query.responsible_user_id = responsibleUserId.value;
    if (areaId.value) query.eap_node_id = areaId.value;
    if (workPackageId.value) query.work_package_id = workPackageId.value;
    const result = await api.get<EquipmentList>("/equipments", query, {
      force: true,
    });
    if (version !== requestVersion) return;
    equipments.value = result.items;
    pagination.value = result.pagination;
  } catch (caught) {
    if (version !== requestVersion) return;
    error.value =
      caught instanceof Error
        ? caught.message
        : "Não foi possível carregar os equipamentos.";
    equipments.value = [];
    pagination.value = null;
  } finally {
    if (version === requestVersion) {
      refreshing.value = false;
      loading.value = false;
    }
  }
}

const disciplineOptions = computed(() => toOptions(disciplines.value));
const responsibleOptions = computed<SearchableOption[]>(() =>
  responsibles.value.map((item) => ({
    id: item.id,
    label: item.name,
    searchText: item.email,
  })),
);
const areaOptions = computed(() => toOptions(areas.value));
const workPackageOptions = computed<SearchableOption[]>(() =>
  workPackages.value.map((item) => ({
    id: item.id,
    label: item.code ?? item.name,
    description: item.description?.trim() || "WP sem descrição",
    searchText: item.name,
  })),
);

async function reload(): Promise<void> {
  page.value = 1;
  await syncQuery();
  await load();
}

/** Unidade/Obra/Equipamento globais mudaram: recarrega Área/WP antes da lista,
 * para nunca filtrar por uma seleção que já deixou de existir na unidade
 * nova. */
async function onGlobalFilterChange(): Promise<void> {
  if (editingTable.value &&
    (context.selectedUnit !== editorUnitId.value ||
     context.selectedProjectContext !== editorProjectContextId.value)) {
    if (bulkEditorRef.value?.hasPending() && !bulkEditorRef.value.confirmDiscard()) {
      await context.setUnit(editorUnitId.value);
      await context.setProjectContext(editorProjectContextId.value);
      return;
    }
    editingTable.value = false;
  }
  await loadAreaAndWorkPackageOptions();
  await reload();
}

/** Monta a consulta do recorte atual; `pageSize` alto traz o conjunto filtrado. */
function currentQuery(pageSize: number, page: number): Record<string, unknown> {
  const query: Record<string, unknown> = {
    ...context.apiQuery,
    page,
    pageSize,
    sortBy: "name",
  };
  if (stage.value !== "") query.stage = Number(stage.value);
  if (disciplineId.value) query.discipline_id = disciplineId.value;
  if (responsibleUserId.value)
    query.responsible_user_id = responsibleUserId.value;
  if (areaId.value) query.eap_node_id = areaId.value;
  if (workPackageId.value) query.work_package_id = workPackageId.value;
  return query;
}

async function exportAll(): Promise<void> {
  if (exporting.value) return;
  exporting.value = true;
  exportProgress.value = "";
  error.value = "";
  try {
    // Percorre as páginas do recorte para não exportar só o que está na tela.
    const rows = await collectAllPages<Equipment>(
      (page) => api.get<EquipmentList>("/equipments", currentQuery(100, page)),
      {
        onProgress: (currentPage, totalPages) => {
          exportProgress.value =
            totalPages > 1
              ? `Exportando página ${currentPage} de ${totalPages}...`
              : "";
        },
      },
    );

    await useExport().excel(
      `equipamentos-${new Date().toISOString().slice(0, 10)}`,
      rows,
    );
  } catch (caught) {
    error.value =
      caught instanceof Error ? caught.message : "Não foi possível exportar.";
  } finally {
    exporting.value = false;
    exportProgress.value = "";
  }
}

async function saved(_equipment: Equipment): Promise<void> {
  showForm.value = false;
  await context.loadEquipmentOptions();
  await load();
}

async function realtimeChanged(event: RealtimeChangeEvent): Promise<void> {
  const relevantEquipment =
    event.entityType === "equipment" &&
    (!context.selectedUnit || event.unitId === context.selectedUnit) &&
    (!context.selectedProjectContext ||
      event.projectContextId === context.selectedProjectContext);
  const relevantProject =
    event.entityType === "project_context" &&
    (!context.selectedUnit || event.unitId === context.selectedUnit);
  if (
    event.eventType !== "revalidate" &&
    !relevantEquipment &&
    !relevantProject
  )
    return;
  quietRefresh = true;
  await load();
}

onMounted(async () => {
  unsubscribeSync = realtime.subscribe(realtimeChanged);
  if (!allowed.value) {
    loading.value = false;
    return;
  }
  await context.initialize({
    unit: typeof route.query.unit === "string" ? route.query.unit : undefined,
    project:
      typeof route.query.project === "string" ? route.query.project : undefined,
    equipment:
      typeof route.query.equipment === "string"
        ? route.query.equipment
        : undefined,
  });
  disciplines.value = (
    await api.get<CatalogList<CatalogItem>>("/disciplines")
  ).items;
  criticalityLabels.value = (
    await api.get<CatalogList<CatalogItem>>("/criticality-labels")
  ).items;
  if (context.selectedUnit) {
    responsibles.value = (
      await api.get<CatalogList<Responsible>>("/responsibles", {
        unit_id: context.selectedUnit,
      })
    ).items;
  }
  await loadAreaAndWorkPackageOptions();
  await syncQuery();
  await load();
});
onBeforeUnmount(() => unsubscribeSync?.());
</script>

<template>
  <ModuleWorkspace
    eyebrow="Planejamento · Equipamentos"
    title="Equipamentos"
    description="Listagem operacional com filtros e acesso ao detalhe do processo."
  >
    <div v-if="!allowed" class="surface empty-state state-card" role="alert">
      <h2>Sem permissão</h2>
      <p>Seu perfil não tem acesso à leitura de equipamentos.</p>
    </div>
    <div v-else class="stack">
      <ModuleFilters
        show-project-context
        :refreshing="refreshing || loading"
        @change="onGlobalFilterChange"
        @refresh="load"
      >
        <template #actions>
          <VBtn
            v-if="canAdminister"
            variant="outlined"
            color="secondary"
            size="default"
            data-testid="admin-button"
            :prepend-icon="mdiTuneVariant"
            @click="showAdmin = true"
          >
            Administração
          </VBtn>
          <VBtn
            variant="outlined"
            color="info"
            size="default"
            :disabled="loading"
            :loading="exporting"
            data-testid="export-button"
            :prepend-icon="!exporting ? mdiCloudDownloadOutline : undefined"
            @click="exportAll"
          >
            {{ exporting ? exportProgress || "Exportando..." : "Exportar" }}
          </VBtn>
          <VBtn
            v-if="auth.can('equipments:write')"
            variant="flat"
            color="primary"
            size="default"
            :disabled="!canCreate"
            :title="
              !context.selectedUnit
                ? 'Selecione uma unidade para cadastrar'
                : undefined
            "
            :prepend-icon="mdiPlus"
            @click="showForm = true"
          >
            Novo equipamento
          </VBtn>
          <VBtn
            variant="outlined"
            size="default"
            :disabled="!canGenerateReport || loading"
            :title="!canGenerateReport ? 'Selecione uma unidade com obras para gerar o report' : 'Escolher obras para o relatório executivo'"
            data-testid="generate-report-button"
            @click="openExecutiveReport"
          >
            <Sparkles class="text-[12px] opacity-60 mr-1" /> Gerar Report
          </VBtn>
        </template>
      </ModuleFilters>

      <section class="surface">
        <div class="surface-header">
          <div>
            <h2>Resultados</h2>
            <p>{{ pagination?.total ?? 0 }} registro(s) encontrado(s).</p>
          </div>
        </div>
        <div class="table-filters">
          <div class="inline-field">
            <FloatingFilterSelect
              v-model="stage"
              :options="STAGE_OPTIONS"
              :sorted="false"
              :icon="mdiLayers"
              label="Etapa"
              placeholder="Buscar etapa"
              empty-label="Todas"
              density="compact"
              @change="reload"
            />
          </div>
          <div class="inline-field">
            <FloatingFilterSelect
              v-model="disciplineId"
              :options="disciplineOptions"
              :icon="mdiTag"
              label="Disciplina"
              placeholder="Buscar disciplina"
              empty-label="Todas"
              density="compact"
              @change="reload"
            />
          </div>
          <div class="inline-field">
            <FloatingFilterSelect
              v-model="responsibleUserId"
              :options="responsibleOptions"
              :disabled="!context.selectedUnit"
              :title="
                !context.selectedUnit
                  ? 'Selecione uma unidade para filtrar por responsável'
                  : undefined
              "
              :icon="mdiAccount"
              label="Responsável"
              placeholder="Buscar responsável"
              empty-label="Todos"
              density="compact"
              test-id="responsible-filter"
              @change="reload"
            />
          </div>
          <div class="inline-field">
            <FloatingFilterSelect
              v-model="areaId"
              :options="areaOptions"
              :icon="mdiMapMarker"
              label="Área"
              placeholder="Buscar por código ou nome"
              empty-label="Todas"
              density="compact"
              test-id="area-filter"
              @change="reload"
            />
          </div>
          <div class="inline-field">
            <FloatingFilterSelect
              v-model="workPackageId"
              :options="workPackageOptions"
              :disabled="!context.selectedUnit"
              :title="
                !context.selectedUnit
                  ? 'Selecione uma unidade para filtrar por Work Package'
                  : undefined
              "
              :icon="mdiPackageVariant"
              label="Work Package"
              placeholder="Buscar por código ou descrição"
              empty-label="Todos"
              density="compact"
              test-id="work-package-filter"
              @change="reload"
            />
          </div>
          <VBtn
            v-if="auth.can('equipments:write')"
            variant="tonal"
            color="primary"
            :disabled="!canEditTable && !editingTable"
            :title="!canEditTable ? 'Selecione uma obra para editar' : undefined"
            data-testid="toggle-equipment-table-edit"
            @click="toggleTableEditing">
            {{ editingTable ? "Sair da edição" : "Editar tabela" }}
          </VBtn>
        </div>

        <div
          v-if="error && !loading"
          class="empty-state table-empty"
          role="alert"
        >
          <h2>Não foi possível carregar</h2>
          <p>{{ error }}</p>
          <VBtn variant="outlined" @click="load">Tentar novamente</VBtn>
        </div>
        <template v-else>
          <EquipmentBulkEditor
            v-if="editingTable"
            ref="bulkEditorRef"
            :equipments="equipments"
            :project-context-id="editorProjectContextId"
            :filters="currentQuery(100, 1)"
            :total="pagination?.total ?? 0"
            :discipline-options="disciplineOptions"
            :responsible-options="responsibleOptions"
            :eap-options="areaOptions"
            :work-package-options="workPackageOptions"
            :criticality-options="criticalityLabels.map((item) => ({ id: item.id, label: item.name }))"
            @saved="editorSaved"
            @exit="editingTable = false"
          />
          <EquipmentTable
            v-else
            :equipments="equipments"
            :loading="loading || refreshing"
          />
          <AppPagination
            v-if="pagination && pagination.totalPages > 1"
            class="pagination"
            :page="page"
            :total-pages="pagination.totalPages"
            :disabled="refreshing"
            @change="onPageChange"
          />
        </template>
      </section>
    </div>

    <EquipmentAdmin
      v-if="canAdminister"
      :open="showAdmin"
      :unit-id="context.selectedUnit"
      @close="showAdmin = false"
      @changed="adminChanged"
    />

    <AppModal
      :open="showForm"
      title="Novo equipamento"
      size="wide"
      @close="showForm = false"
    >
      <EquipmentForm
        v-if="showForm && context.selectedUnit"
        :unit-id="context.selectedUnit"
        @saved="saved"
        @cancel="showForm = false"
      />
    </AppModal>

    <VDialog v-model="showReportPicker" max-width="520" scrollable>
      <VCard rounded="lg" data-testid="report-project-picker">
        <VCardTitle class="px-6 pt-5">Selecionar obras do relatório</VCardTitle>
        <VCardText class="px-6">
          <p class="report-picker-description">
            Selecione uma ou mais obras da unidade {{ context.selectedUnitLabel }}.
            O relatório consolidará todos os equipamentos das obras escolhidas.
          </p>
          <div class="report-picker-actions">
            <VBtn size="small" variant="text" @click="selectedReportProjectIds = availableReportProjects.map((project) => project.id)">
              Selecionar todas
            </VBtn>
            <VBtn size="small" variant="text" @click="selectedReportProjectIds = []">
              Limpar
            </VBtn>
          </div>
          <VCheckbox
            v-for="project in availableReportProjects"
            :key="project.id"
            :model-value="selectedReportProjectIds.includes(project.id)"
            :label="project.name"
            color="primary"
            density="compact"
            hide-details
            class="report-picker-checkbox"
            @update:model-value="toggleReportProject(project.id, Boolean($event))"
          />
        </VCardText>
        <VCardActions class="px-6 pb-5">
          <span class="report-picker-count">{{ selectedReportProjectIds.length }} selecionada(s)</span>
          <VSpacer />
          <VBtn variant="text" @click="showReportPicker = false">Cancelar</VBtn>
          <VBtn
            color="primary"
            variant="flat"
            data-testid="confirm-report-projects"
            :disabled="selectedReportProjectIds.length === 0"
            @click="confirmExecutiveReport()"
          >
            Gerar relatório
          </VBtn>
        </VCardActions>
      </VCard>
    </VDialog>

    <EquipmentExecutiveReport
      v-if="reportSelection"
      :key="`${reportSelection.unitId}-${reportSelection.projectContextIds.join(',')}`"
      :unit-id="reportSelection.unitId"
      :project-context-id="reportSelection.projectContextId"
      :project-context-ids="reportSelection.projectContextIds"
      :unit-name="reportSelection.unitName"
      :project-name="reportSelection.projectName"
      @close="reportSelection = null"
    />
  </ModuleWorkspace>
</template>

<style scoped>
.state-card {
  max-width: none;
}
.report-picker-description {
  color: #61738a;
  font-size: 13px;
  line-height: 1.6;
  margin-bottom: 12px;
}
.report-picker-actions {
  display: flex;
  justify-content: flex-end;
  gap: 4px;
  margin-bottom: 8px;
}
.report-picker-checkbox {
  border-radius: 8px;
}
.report-picker-count {
  color: #61738a;
  font-size: 12px;
}

.table-filters {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 12px;
  padding: 18px 18px 16px;
}
.inline-field {
  display: block;
  min-width: 0;
}
.queue-state {
  display: flex;
  min-height: 220px;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: #748197;
}
.table-empty {
  margin: auto;
  padding-bottom: 28px;
}
.pagination {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  padding: 0 18px 18px;
  color: #68778c;
  font-size: 12px;
}
/* Notebook: filtros da tabela mais compactos, quebrando em mais linhas antes
   de apertar as colunas. */
@media (max-width: 1100px) {
  .table-filters {
    grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
    padding: 14px 14px 12px;
  }
}
</style>
