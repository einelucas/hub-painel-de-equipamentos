<script setup lang="ts">
import {
  CloudDownload,
  Plus,
  Search,
  SlidersHorizontal,
} from "lucide-vue-next";
import type {
  CatalogItem,
  CatalogList,
  Equipment,
  EquipmentList,
  Pagination,
  Responsible,
} from "~/types/equipment";
import { formatDateOnly } from "~/utils/format";
import { equipmentLocationLabel } from "~/utils/equipmentLocation";
import { loadEapLocationOptions } from "~/utils/eapLocationOptions";
import SearchableSelect from "~/components/ui/SearchableSelect.vue";
import Button from "~/components/ui/Button.vue";
import type { SearchableOption } from "~/types/ui";
import { STAGE_OPTIONS, toOptions } from "~/utils/selectOptions";
import { collectAllPages } from "~/utils/pagination";

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
const search = ref("");
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
let requestVersion = 0;

const allowed = computed(() => auth.can("equipments:read"));
const canCreate = computed(
  () => auth.can("equipments:write") && Boolean(context.selectedUnit),
);
// Administração contextual: só aparece para quem realmente pode administrar.
const canAdminister = computed(
  () => auth.can("catalogs:manage") || auth.can("users:manage"),
);

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
  if (context.selectedProjectContext) query.project = context.selectedProjectContext;
  else delete query.project;
  if (context.selectedEquipment) query.equipment = context.selectedEquipment;
  else delete query.equipment;
  await router.replace({ query });
}

/** Troca de página pela paginação do Element Plus. */
function onPageChange(next: number): void {
  page.value = next;
  void load();
}

async function load(): Promise<void> {
  const version = ++requestVersion;
  refreshing.value = true;
  error.value = "";
  try {
    const query: Record<string, unknown> = {
      ...context.apiQuery,
      page: page.value,
      pageSize: 25,
      sortBy: "name",
    };
    if (search.value.trim()) query.search = search.value.trim();
    if (stage.value !== "") query.stage = Number(stage.value);
    if (disciplineId.value) query.discipline_id = disciplineId.value;
    if (responsibleUserId.value)
      query.responsible_user_id = responsibleUserId.value;
    if (areaId.value) query.eap_node_id = areaId.value;
    if (workPackageId.value) query.work_package_id = workPackageId.value;
    const result = await api.get<EquipmentList>("/equipments", query);
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
  responsibles.value.map((item) => ({ id: item.id, label: item.name, searchText: item.email })),
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
  if (search.value.trim()) query.search = search.value.trim();
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
      (page) => api.get<EquipmentList>(
        "/equipments",
        currentQuery(100, page),
      ),
      {
        onProgress: (currentPage, totalPages) => {
          exportProgress.value = totalPages > 1
            ? `Exportando página ${currentPage} de ${totalPages}...`
            : "";
        },
      },
    );

    useExport().excel(
      `equipamentos-${new Date().toISOString().slice(0, 10)}`,
      rows.map((item) => ({
        Equipamento: item.name,
        Unidade: item.unit.name,
        Contexto: item.projectContext.code ?? item.projectContext.name,
        Área: equipmentLocationLabel(item) ?? "",
        Disciplina: item.discipline?.name ?? "",
        "Work Packages": item.workPackages
          .map((wp) => wp.code ?? wp.name)
          .join(", "),
        Responsável: item.responsibleUser?.name ?? "",
        Etapa: `${item.currentStage} · ${item.stageName}`,
        Startup: formatDateOnly(item.startupAt),
        Criticidade: item.criticalityLabel?.name ?? item.criticality ?? "",
        Componentes: item.componentsCount,
      })),
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

onMounted(async () => {
  if (!allowed.value) {
    loading.value = false;
    return;
  }
  await context.initialize({
    unit: typeof route.query.unit === "string" ? route.query.unit : undefined,
    project:
      typeof route.query.project === "string"
        ? route.query.project
        : undefined,
    equipment:
      typeof route.query.equipment === "string"
        ? route.query.equipment
        : undefined,
  });
  disciplines.value = (
    await api.get<CatalogList<CatalogItem>>("/disciplines")
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
</script>

<template>
  <ModuleWorkspace
    eyebrow="Planejamento · Equipamentos"
    title="Equipamentos"
    description="Listagem operacional com busca, filtros e acesso ao detalhe do processo."
  >
    <div v-if="!allowed" class="surface empty-state state-card" role="alert">
      <h2>Sem permissão</h2>
      <p>Seu perfil não tem acesso à leitura de equipamentos.</p>
    </div>
    <div v-else class="stack">
      <ModuleFilters show-project-context :refreshing="refreshing" @change="onGlobalFilterChange">
        <form class="field field-wide" @submit.prevent="reload">
          <span>Busca</span>
          <div class="search-control">
            <input v-model="search" placeholder="Nome do equipamento" />
            <Button variant="outline" type="submit" :loading="refreshing">
              <Search v-if="!refreshing" :size="16" /> Buscar
            </Button>
          </div>
        </form>
        <template #actions>
          <Button
            v-if="canAdminister"
            variant="outline"
            data-testid="admin-button"
            @click="showAdmin = true"
          >
            <SlidersHorizontal :size="16" /> Administração
          </Button>
          <Button
            variant="outline"
            :disabled="loading"
            :loading="exporting"
            data-testid="export-button"
            @click="exportAll"
          >
            <CloudDownload v-if="!exporting" :size="16" />
            {{ exporting ? (exportProgress || "Exportando...") : "Exportar" }}
          </Button>
          <Button
            v-if="auth.can('equipments:write')"
            variant="default"
            :disabled="!canCreate"
            :title="
              !context.selectedUnit
                ? 'Selecione uma unidade para cadastrar'
                : undefined
            "
            @click="showForm = true"
          >
            <Plus :size="16" /> Novo equipamento
          </Button>
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
            <span>Etapa</span>
            <SearchableSelect
              v-model="stage"
              :class="{ 'is-set': stage }"
              :options="STAGE_OPTIONS"
              :sorted="false"
              label="Etapa"
              placeholder="Buscar etapa"
              empty-label="Todas"
              @change="reload"
            />
          </div>
          <div class="inline-field">
            <span>Disciplina</span>
            <SearchableSelect
              v-model="disciplineId"
              :class="{ 'is-set': disciplineId }"
              :options="disciplineOptions"
              label="Disciplina"
              placeholder="Buscar disciplina"
              empty-label="Todas"
              @change="reload"
            />
          </div>
          <div class="inline-field">
            <span>Responsável</span>
            <SearchableSelect
              v-model="responsibleUserId"
              :class="{ 'is-set': responsibleUserId }"
              :options="responsibleOptions"
              :disabled="!context.selectedUnit"
              :title="
                !context.selectedUnit
                  ? 'Selecione uma unidade para filtrar por responsável'
                  : undefined
              "
              label="Responsável"
              placeholder="Buscar responsável"
              empty-label="Todos"
              test-id="responsible-filter"
              @change="reload"
            />
          </div>
          <div class="inline-field">
            <span>Área</span>
            <SearchableSelect
              v-model="areaId"
              :class="{ 'is-set': areaId }"
              :options="areaOptions"
              label="Área"
              placeholder="Buscar por código ou nome"
              empty-label="Todas"
              test-id="area-filter"
              @change="reload"
            />
          </div>
          <div class="inline-field">
            <span>Work Package</span>
            <SearchableSelect
              v-model="workPackageId"
              :class="{ 'is-set': workPackageId }"
              :options="workPackageOptions"
              :disabled="!context.selectedUnit"
              :title="
                !context.selectedUnit
                  ? 'Selecione uma unidade para filtrar por Work Package'
                  : undefined
              "
              label="Work Package"
              placeholder="Buscar por código ou descrição"
              empty-label="Todos"
              test-id="work-package-filter"
              @change="reload"
            />
          </div>
        </div>

        <div v-if="loading" class="queue-state" role="status" aria-busy="true">
          <span class="spinner" aria-hidden="true" /> Carregando equipamentos...
        </div>
        <div v-else-if="error" class="empty-state table-empty" role="alert">
          <h2>Não foi possível carregar</h2>
          <p>{{ error }}</p>
          <Button variant="outline" @click="load">Tentar novamente</Button>
        </div>
        <template v-else>
          <div v-if="refreshing" class="progress-indeterminate" role="progressbar" aria-label="Atualizando equipamentos" />
          <EquipmentTable :equipments="equipments" :aria-busy="refreshing" />
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
      @close="showForm = false"
    >
      <EquipmentForm
        v-if="showForm && context.selectedUnit"
        :unit-id="context.selectedUnit"
        @saved="saved"
        @cancel="showForm = false"
      />
    </AppModal>
  </ModuleWorkspace>
</template>

<style scoped>
.state-card {
  max-width: none;
}
.search-control {
  display: flex;
  min-width: 0;
  gap: 7px;
}
/* O input precisa poder encolher; sem isso ele impõe a largura mínima do
   campo de busca e ajuda a estourar a barra de filtros em telas menores. */
.search-control input {
  flex: 1;
  min-width: 0;
}
.search-control .btn {
  flex: none;
}
.table-filters {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 12px;
  padding: 18px 18px 16px;
}
.inline-field {
  display: grid;
  min-width: 0;
  gap: 5px;
}
.inline-field > span {
  color: #7a879a;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}
.table-filters select {
  width: 100%;
  min-height: 36px;
  padding: 7px 30px 7px 10px;
  border: 1px solid #d8e0ea;
  border-radius: 8px;
  /* seta própria: o appearance nativo fica desalinhado com o resto do sistema */
  background: #fff url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%237a879a' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E") no-repeat right 10px center;
  color: #26364d;
  font-size: 13px;
  text-overflow: ellipsis;
  appearance: none;
  outline: none;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.table-filters :deep(.searchable-select__control) {
  min-height: 36px;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.table-filters :deep(.searchable-select__control input) {
  padding: 7px 0;
  font-size: 13px;
}
.table-filters :deep(.searchable-select__control:hover) {
  border-color: #b9c6d6;
}
/* Filtro aplicado fica destacado, como nos selects anteriores. */
.table-filters .is-set :deep(.searchable-select__control) {
  border-color: #9fb5d4;
  background-color: #f2f6fc;
}
.table-filters .is-set :deep(.searchable-select__control input) {
  color: #213758;
  font-weight: 600;
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
    grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
    padding: 14px 14px 12px;
  }
}
</style>
