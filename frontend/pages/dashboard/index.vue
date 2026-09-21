<script setup lang="ts">
import { Boxes, Layers } from "lucide-vue-next";
import type { DashboardSummary } from "~/types/equipment";
import { situationDonut, stageChartPoints, startupLabel } from "~/utils/dashboard";
import { formatCurrency, formatNumber } from "~/utils/format";

definePageMeta({ middleware: "auth" });
const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const api = useApi();
const context = useModuleContextStore();

const summary = ref<DashboardSummary | null>(null);
const loading = ref(true);
const refreshing = ref(false);
const error = ref("");
let requestVersion = 0;

const allowed = computed(() => auth.can("equipments:read"));
const chartPoints = computed(() => stageChartPoints(summary.value?.workflow ?? []));
const donutItems = computed(() => situationDonut(summary.value?.workflow ?? []));
const isEmpty = computed(() => (summary.value?.totals.equipments ?? 0) === 0);

async function syncQuery(): Promise<void> {
  const query: Record<string, string> = { ...(route.query as Record<string, string>) };
  if (context.selectedUnit) query.unit = context.selectedUnit;
  else delete query.unit;
  if (context.selectedEquipment) query.equipment = context.selectedEquipment;
  else delete query.equipment;
  await router.replace({ query });
}

async function load(): Promise<void> {
  const version = ++requestVersion;
  refreshing.value = true;
  error.value = "";
  try {
    const result = await api.get<DashboardSummary>("/dashboard/summary", context.apiQuery);
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
}

async function reload(): Promise<void> {
  await syncQuery();
  await load();
}

onMounted(async () => {
  if (!allowed.value) {
    loading.value = false;
    return;
  }
  await context.initialize({
    unit: typeof route.query.unit === "string" ? route.query.unit : undefined,
    equipment: typeof route.query.equipment === "string" ? route.query.equipment : undefined,
  });
  await syncQuery();
  await load();
});
</script>

<template>
  <ModuleWorkspace
    eyebrow="Planejamento · Equipamentos"
    title="Dashboard Geral"
    description="Visão consolidada do processo de aquisição e acompanhamento dos equipamentos."
  >
    <div v-if="!allowed" class="surface empty-state state-card" role="alert" data-testid="dashboard-forbidden">
      <h2>Sem permissão</h2><p>Seu perfil não tem acesso à leitura de equipamentos deste módulo.</p>
    </div>
    <div v-else class="stack">
      <ModuleFilters :refreshing="refreshing" @change="reload" />

      <div v-if="loading" class="surface loading-state" data-testid="dashboard-loading"><span class="spinner" /><p>Carregando painel...</p></div>
      <div v-else-if="error" class="surface empty-state state-card" role="alert" data-testid="dashboard-error">
        <h2>Não foi possível carregar o painel</h2><p>{{ error }}</p>
        <button class="btn" @click="load">Tentar novamente</button>
      </div>
      <div v-else-if="isEmpty" class="surface empty-state state-card" data-testid="dashboard-empty">
        <h2>Nenhum equipamento no recorte</h2>
        <p>Cadastre um equipamento ou ajuste os filtros de unidade e equipamento.</p>
        <NuxtLink class="btn" to="/equipamentos">Ir para Equipamentos</NuxtLink>
      </div>
      <template v-else-if="summary">
        <section class="metric-grid" aria-label="Indicadores do recorte atual">
          <MetricCard label="Equipamentos" :value="formatNumber(summary.totals.equipments, 0)" detail="No recorte atual" />
          <MetricCard label="Componentes" :value="formatNumber(summary.totals.components, 0)" detail="Subitens cadastrados" />
          <MetricCard label="Em andamento" :value="formatNumber(summary.totals.inProgress, 0)" detail="Etapas 0 a 7" />
          <MetricCard label="Concluídos" :value="formatNumber(summary.totals.completed, 0)" detail="Etapa 8" tone="good" />
          <MetricCard label="Valor emitido em OC" :value="formatCurrency(summary.totals.purchaseOrderAmount)" :detail="`${formatNumber(summary.totals.purchaseOrders, 0)} OC(s) emitida(s)`" />
          <MetricCard label="CAPEX estimado" :value="formatCurrency(summary.totals.capexEstimated)" detail="Soma dos valores informados" />
        </section>

        <div class="chart-row">
          <section class="surface chart-surface">
            <div class="surface-header"><div><h2><Layers :size="15" /> Distribuição por etapa</h2><p>Quantidade de equipamentos em cada estágio do fluxo 0–8.</p></div></div>
            <div class="surface-body"><BarChart :points="chartPoints" suffix="" series-label="Equipamentos" :show-legend="false" /></div>
          </section>

          <section class="surface chart-surface">
            <div class="surface-header"><div><h2><Boxes :size="15" /> Situação geral</h2><p>Agrupamento do mesmo catálogo de etapas.</p></div></div>
            <div class="surface-body"><DonutChart :items="donutItems" suffix="" :show-legend-values="true" /></div>
          </section>
        </div>

        <div class="dashboard-cards-grid">
          <NegotiationCard :negotiation="summary.negotiation" />
          <DeadlineStatusCard :deadlines="summary.deadlines" />
          <NextStartupCard :startup="summary.startup" :label="startupLabel(summary)" />
        </div>

        <div class="dashboard-cards-grid">
          <NegotiationDeadlineStatusCard :summary="summary.negotiationDeadlineStatus" />
        </div>
      </template>
    </div>
  </ModuleWorkspace>
</template>

<style scoped>
.state-card { max-width: none; }
/* A linha mistura contagens e moeda: cards um pouco mais largos e fonte menor
   mantêm "R$ 125.000,00" em uma única linha. */
.metric-grid { grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); }
.metric-grid :deep(.metric-card .value) { font-size: 20px; white-space: nowrap; }
.state-card .btn { margin-top: 18px; }
.loading-state { display: grid; min-height: 320px; place-items: center; align-content: center; gap: 10px; color: #748197; }
.chart-row { display: grid; grid-template-columns: minmax(0, 1.55fr) minmax(0, 1fr); gap: 18px; align-items: start; }
.surface-header h2 { display: inline-flex; align-items: center; gap: 7px; }
.chart-surface .surface-body { padding: 8px 20px 2px; }
/* Grid dos 3 cards (Negociação / Situação de prazos / Próxima startup):
   align-items: stretch garante que os três acompanhem a altura do maior
   (normalmente "Situação de prazos", que tem mais conteúdo) — nenhuma
   altura fixa é definida manualmente em nenhum dos cards. */
.dashboard-cards-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); align-items: stretch; gap: 18px; }
@media (max-width: 1100px) { .chart-row { grid-template-columns: 1fr; } }
@media (max-width: 1099px) { .dashboard-cards-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 699px) { .dashboard-cards-grid { grid-template-columns: 1fr; } }
</style>
