<script setup lang="ts">
import { ChartNoAxesCombined, CalendarDays, MapPinned } from "lucide-vue-next";
import { VBtn, VTab, VTabs } from "vuetify/components";
import type { CatalogItem, CatalogList, DashboardSummary } from "~/types/equipment";
import type { DashboardAnalytics } from "~/types/dashboardAnalytics";
import CardProgress from "~/components/ui/CardProgress.vue";
import { situationDonut, startupLabel } from "~/utils/dashboard";
import DashboardSituationDonut from "~/components/dashboard/DashboardSituationDonut.vue";
import { formatCurrency, formatNumber } from "~/utils/format";
import { loadEapLocationOptions } from "~/utils/eapLocationOptions";
import type { RealtimeChangeEvent } from "~/composables/useRealtimeSync";

definePageMeta({ middleware: "auth" });
const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const api = useApi();
const context = useModuleContextStore();
const dashboard = useDashboardFilters();

const areas = ref<CatalogItem[]>([]);
const disciplines = ref<CatalogItem[]>([]);
const summary = ref<DashboardSummary | null>(null);
const analytics = ref<DashboardAnalytics | null>(null);
const loading = ref(true);
const refreshing = ref(false);
const analyticsLoading = ref(false);
const error = ref("");
const analyticsError = ref("");
const analysisTab = ref("eap");
let requestVersion = 0;
let quietRefresh = false;
let unsubscribeSync: (() => void) | null = null;
const realtime = useRealtimeSync();

const allowed = computed(() => auth.can("equipments:read"));
const donutItems = computed(() => situationDonut(summary.value?.workflow ?? []));
const isEmpty = computed(() => (summary.value?.totals.equipments ?? 0) === 0);
const highRisk = computed(() => {
  const d = summary.value?.deadlines;
  return d ? d.checkDeliveryFup + d.neededToday + d.lt30Days : 0;
});

async function syncQuery(): Promise<void> {
  const query: Record<string, string> = { ...(route.query as Record<string, string>) };
  if (context.selectedUnit) query.unit = context.selectedUnit;
  else delete query.unit;
  if (context.selectedProjectContext) query.project = context.selectedProjectContext;
  else delete query.project;
  if (context.selectedEquipment) query.equipment = context.selectedEquipment;
  else delete query.equipment;
  dashboard.writeRouteQuery(query);
  await router.replace({ query });
}

/** Falha de catálogos não impede acesso ao painel. */
async function loadDisciplines(): Promise<void> {
  try {
    disciplines.value = (await api.get<CatalogList<CatalogItem>>("/disciplines")).items;
  } catch {
    disciplines.value = [];
  }
}

async function loadAreas(): Promise<void> {
  try {
    areas.value = await loadEapLocationOptions(api);
  } catch {
    areas.value = [];
  }
  if (!areas.value.some((item) => item.id === dashboard.filters.areaId)) {
    dashboard.filters.areaId = null;
  }
}

/**
 * As duas APIs usam o mesmo recorte e podem ser carregadas em paralelo.
 * A falha de /analytics não cancela o resumo operacional nem os filtros.
 */
async function load(): Promise<void> {
  const version = ++requestVersion;
  const quiet = quietRefresh;
  quietRefresh = false;
  if (!quiet) {
    refreshing.value = true;
    analytics.value = null;
  }
  analyticsLoading.value = true;
  analyticsError.value = "";
  error.value = "";
  const query = { ...context.apiQuery, ...dashboard.apiQuery.value };

  const analyticsRequest = api.get<DashboardAnalytics>("/dashboard/analytics", query, { force: true })
    .then((value) => {
      if (version === requestVersion) analytics.value = value;
    })
    .catch((caught: unknown) => {
      if (version !== requestVersion) return;
      analyticsError.value = caught instanceof Error
        ? caught.message
        : "Não foi possível carregar as análises complementares.";
    })
    .finally(() => {
      if (version === requestVersion) analyticsLoading.value = false;
    });

  try {
    const result = await api.get<DashboardSummary>("/dashboard/summary", query, { force: true });
    if (version !== requestVersion) return;
    summary.value = result;
  } catch (caught) {
    if (version !== requestVersion) return;
    error.value = caught instanceof Error ? caught.message : "Não foi possível carregar o painel.";
    summary.value = null;
  } finally {
    if (version === requestVersion) {
      refreshing.value = false;
      loading.value = false;
    }
  }
  await analyticsRequest;
}

async function reload(): Promise<void> {
  await loadAreas();
  await syncQuery();
  await load();
}

async function applyDashboardFilters(): Promise<void> {
  await syncQuery();
  await load();
}

async function clearDashboardFilters(): Promise<void> {
  dashboard.clear();
  await applyDashboardFilters();
}

async function filterByStage(stage: number): Promise<void> {
  dashboard.filters.stage = dashboard.filters.stage === stage ? null : stage;
  await applyDashboardFilters();
}

async function realtimeChanged(event: RealtimeChangeEvent): Promise<void> {
  const relevant = event.eventType === "revalidate" ||
    ((event.entityType === "equipment" || event.entityType === "project_context") &&
      (!context.selectedUnit || event.unitId === context.selectedUnit) &&
      (!context.selectedProjectContext || event.projectContextId === context.selectedProjectContext));
  if (!relevant || loading.value) return;
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
    project: typeof route.query.project === "string" ? route.query.project : undefined,
    equipment: typeof route.query.equipment === "string" ? route.query.equipment : undefined,
  });
  dashboard.readRouteQuery(route.query);
  await Promise.all([loadDisciplines(), loadAreas()]);
  await syncQuery();
  await load();
});
onBeforeUnmount(() => unsubscribeSync?.());
</script>

<template>
  <ModuleWorkspace
    eyebrow="Planejamento · Equipamentos"
    title="Dashboard Geral"
    description="Visão consolidada de aquisições, riscos e acompanhamento dos equipamentos."
  >
    <div v-if="!allowed" class="surface empty-state state-card" role="alert" data-testid="dashboard-forbidden">
      <h2>Sem permissão</h2>
      <p>Seu perfil não tem acesso à leitura de equipamentos deste módulo.</p>
    </div>
    <div v-else class="stack dashboard-v2">
      <ModuleFilters show-project-context :refreshing="refreshing || loading" @change="reload" @refresh="load">
        <DashboardFilters
          v-model:area-id="dashboard.filters.areaId"
          v-model:discipline-id="dashboard.filters.disciplineId"
          v-model:stage="dashboard.filters.stage"
          :areas="areas"
          :disciplines="disciplines"
          @change="applyDashboardFilters"
          @clear="clearDashboardFilters"
        />
      </ModuleFilters>

      <div v-if="loading" class="stack" data-testid="dashboard-loading" role="status" aria-busy="true">
        <p class="sr-only">Carregando painel...</p>
        <section class="metric-grid" aria-hidden="true">
          <div v-for="n in 6" :key="n" class="surface skeleton-card">
            <CardProgress /><SkeletonBlock :lines="3" />
          </div>
        </section>
        <div class="chart-row" aria-hidden="true">
          <div v-for="n in 2" :key="n" class="surface skeleton-card tall">
            <CardProgress /><SkeletonBlock :lines="6" />
          </div>
        </div>
      </div>
      <div v-else-if="error" class="surface empty-state state-card" role="alert" data-testid="dashboard-error">
        <h2>Não foi possível carregar o painel</h2><p>{{ error }}</p>
        <VBtn variant="outlined" @click="load">Tentar novamente</VBtn>
      </div>
      <div v-else-if="isEmpty" class="surface empty-state state-card" data-testid="dashboard-empty">
        <h2>Nenhum equipamento no recorte</h2>
        <p v-if="dashboard.hasActive.value">Nenhum equipamento atende à combinação de área, fase e disciplina selecionada.</p>
        <p v-else>Cadastre um equipamento ou ajuste os filtros de unidade e equipamento.</p>
        <VBtn class="state-action" to="/equipamentos" variant="outlined">Ir para Equipamentos</VBtn>
      </div>
      <template v-else-if="summary">
        <p v-if="refreshing" class="sr-only" role="status">Atualizando painel...</p>
        <section class="metric-grid" :aria-busy="refreshing" aria-label="Indicadores do recorte atual">
          <MetricCard label="Equipamentos" :value="formatNumber(summary.totals.equipments, 0)" detail="No recorte atual" :loading="refreshing" />
          <MetricCard label="Componentes" :value="formatNumber(summary.totals.components, 0)" detail="Subitens cadastrados" :loading="refreshing" />
          <MetricCard label="Em andamento" :value="formatNumber(summary.totals.inProgress, 0)" detail="Etapas 0 a 7" :loading="refreshing" />
          <MetricCard label="Concluídos" :value="formatNumber(summary.totals.completed, 0)" detail="Etapa 8" tone="good" :loading="refreshing" />
          <MetricCard label="Prazos críticos" :value="formatNumber(highRisk, 0)" detail="Classificação oficial da necessidade" :tone="highRisk ? 'bad' : 'default'" :loading="refreshing" />
          <MetricCard label="Valor emitido em OC" :value="formatCurrency(summary.totals.purchaseOrderAmount)" :detail="`${formatNumber(summary.totals.purchaseOrders, 0)} OC(s) emitida(s)`" :loading="refreshing" />
        </section>

        <div class="chart-row chart-row--main">
          <DashboardStageBars :workflow="summary.workflow" :selected-stage="dashboard.filters.stage" @select-stage="filterByStage" />
          <DashboardChartFrame title="Situação geral" subtitle="Nova demanda, em processo e concluídos no recorte atual.">
            <DashboardSituationDonut :items="donutItems" suffix="" />
          </DashboardChartFrame>
        </div>

        <div class="dashboard-cards-grid">
          <DashboardNegotiationGauge :negotiation="summary.negotiation" :loading="refreshing" />
          <DashboardDeadlineStack :deadlines="summary.deadlines" :loading="refreshing" />
          <NextStartupCard :startup="summary.startup" :label="startupLabel(summary)" :loading="refreshing" />
        </div>

        <div class="chart-row">
          <DashboardNegotiationDeadlineBars :summary="summary.negotiationDeadlineStatus" :loading="refreshing" />
          <DashboardChartFrame title="Confiabilidade dos prazos" subtitle="Cobertura da informação disponível para os cálculos.">
            <div class="coverage">
              <div class="coverage-item"><span>Com prazo de entrega calculável</span><strong>{{ formatNumber(summary.deadlines.withDeadline, 0) }}</strong></div>
              <div class="coverage-item"><span>Sem prazo de entrega calculável</span><strong>{{ formatNumber(summary.deadlines.withoutDeadline, 0) }}</strong></div>
              <div class="coverage-item"><span>Sem prazo de negociação calculável</span><strong>{{ formatNumber(summary.negotiationDeadlineStatus.notCalculable, 0) }}</strong></div>
              <p>Equipamentos sem dados de referência são sinalizados; o Hub não cria prazos presumidos.</p>
            </div>
          </DashboardChartFrame>
        </div>

        <section class="analytics-section" aria-label="Análises complementares">
          <div class="analytics-head">
            <div>
              <p class="section-kicker">Análises complementares</p>
              <h2>Explore o andamento por diferentes perspectivas</h2>
              <p>Os gráficos abaixo respeitam os mesmos filtros dos indicadores acima.</p>
            </div>
          </div>
          <VTabs v-model="analysisTab" color="primary" density="compact" show-arrows class="analytics-tabs">
            <VTab value="eap"><MapPinned :size="15" aria-hidden="true" /> Áreas e projetos</VTab>
            <VTab value="schedule"><CalendarDays :size="15" aria-hidden="true" /> Entregas</VTab>
            <VTab value="finance"><ChartNoAxesCombined :size="15" aria-hidden="true" /> Financeiro e evolução</VTab>
          </VTabs>

          <div v-if="analyticsError" class="surface analytics-error" role="alert">
            <p>Não foi possível carregar as análises complementares: {{ analyticsError }}</p>
            <VBtn size="small" color="primary" variant="outlined" @click="load">Tentar novamente</VBtn>
          </div>
          <template v-else>
            <div v-if="analysisTab === 'eap'" class="analytics-grid">
              <DashboardDistributionBars
                title="Equipamentos por disciplina"
                subtitle="Quantidade por disciplina cadastrada, inclusive não classificados."
                :items="analytics?.byDiscipline ?? []"
                :loading="analyticsLoading"
              />
              <DashboardDistributionBars
                title="Equipamentos por obra"
                subtitle="Projetos separados por unidade, dentro das permissões do usuário."
                :items="analytics?.byProject ?? []"
                :loading="analyticsLoading"
              />
              <DashboardEapHeatmap :items="analytics?.byEapStage ?? []" :loading="analyticsLoading" />
              <DashboardEapRiskBars :items="analytics?.riskByEap ?? []" :loading="analyticsLoading" />
            </div>
            <div v-else-if="analysisTab === 'schedule'" class="analytics-grid analytics-grid--single">
              <DashboardTimeline
                :windows="analytics?.deliveryWindows ?? []"
                :startups="analytics?.upcomingStartups ?? []"
                :incomplete-count="analytics?.incompleteDeliveryWindows ?? 0"
                :loading="analyticsLoading"
              />
            </div>
            <div v-else class="analytics-grid">
              <DashboardFinancialChart
                :months="analytics?.monthlyPurchaseOrders ?? []"
                :without-date="analytics?.purchaseOrdersWithoutDate ?? 0"
                :without-amount="analytics?.purchaseOrdersWithoutAmount ?? 0"
                :loading="analyticsLoading"
              />
              <DashboardCapexBars :stages="analytics?.capexByStage ?? []" :loading="analyticsLoading" />
              <DashboardMovementsLine :months="analytics?.monthlyWorkflowMovements ?? []" :loading="analyticsLoading" />
            </div>
          </template>
        </section>
      </template>
    </div>
  </ModuleWorkspace>
</template>

<style scoped>
.state-card { max-width: none; }
.dashboard-v2 { gap: 18px; }
.metric-grid { grid-template-columns: repeat(auto-fit, minmax(175px, 1fr)); }
.metric-grid :deep(.metric-card .value) { font-size: 20px; white-space: nowrap; }
.state-action { margin-top: 18px; }
.skeleton-card { padding: 16px 18px; position: relative; overflow: hidden; }
.skeleton-card.tall { min-height: 260px; }
.chart-row { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 18px; align-items: stretch; }
.chart-row--main { grid-template-columns: minmax(0,1.5fr) minmax(0,1fr); }
.dashboard-cards-grid { display: grid; grid-template-columns: repeat(3,minmax(0,1fr)); align-items: stretch; gap: 18px; }
.coverage { display: grid; gap: 16px; padding: 18px 14px; }
.coverage-item { display: flex; justify-content: space-between; align-items: center; gap: 12px; border-bottom: 1px solid #edf1f5; padding-bottom: 11px; font-size: 12px; color: #607085; }
.coverage-item strong { color: #213758; font-size: 19px; }
.coverage p { margin: 4px 0 0; color: #8995a6; font-size: 11px; line-height: 1.6; }
.analytics-section { display: grid; gap: 14px; margin-top: 12px; }
.analytics-head h2 { margin: 0 0 4px; font-size: 20px; font-weight: 800; color: #213758; }
.analytics-head p { margin: 0; color: #7d8a9e; font-size: 12px; }
.analytics-head .section-kicker { margin-bottom: 6px; color: #52709a; font-weight: 800; font-size: 10px; letter-spacing: 0.08em; text-transform: uppercase; }
.analytics-tabs { background: #fff; border: 1px solid #e9eef4; border-radius: 12px; padding: 2px 7px; }
.analytics-tabs :deep(.v-btn__content) { gap: 7px; }
.analytics-grid { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 18px; align-items: stretch; }
.analytics-grid--single { grid-template-columns: 1fr; }
.analytics-error { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 18px; }
.analytics-error p { margin: 0; color: #ab443f; font-size: 12px; }
@media (max-width: 1110px) { .chart-row,.chart-row--main,.analytics-grid { grid-template-columns: 1fr; } .dashboard-cards-grid { grid-template-columns: repeat(2,minmax(0,1fr)); } }
@media (max-width: 700px) { .dashboard-cards-grid { grid-template-columns: 1fr; } .metric-grid { grid-template-columns: repeat(2,minmax(0,1fr)); } .analytics-head h2 { font-size: 17px; } }
@media (max-width: 440px) { .metric-grid { grid-template-columns: 1fr; } }
</style>
