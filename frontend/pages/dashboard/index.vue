<script setup lang="ts">
import { Boxes, CalendarClock, CheckCircle2, Clock, Layers, Receipt } from "lucide-vue-next";
import type { DashboardSummary, WorkNeedStatus } from "~/types/equipment";
import { negotiationProgress, situationDonut, stageChartPoints, startupLabel } from "~/utils/dashboard";
import { formatCurrency, formatDateOnly, formatNumber } from "~/utils/format";
import { workNeedStatusLabel, workNeedStatusTone } from "~/utils/workNeedStatus";

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
const progress = computed(() => (summary.value ? negotiationProgress(summary.value) : null));
const isEmpty = computed(() => (summary.value?.totals.equipments ?? 0) === 0);

// Ordem de prioridade visual explícita (Etapa 6C.1): mais urgente primeiro.
const DEADLINE_ROWS: { status: WorkNeedStatus; field: keyof DashboardSummary["deadlines"] }[] = [
  { status: "CHECK_DELIVERY_FUP", field: "checkDeliveryFup" },
  { status: "NEEDED_TODAY", field: "neededToday" },
  { status: "LT_30_DAYS", field: "lt30Days" },
  { status: "LT_60_DAYS", field: "lt60Days" },
  { status: "LT_90_DAYS", field: "lt90Days" },
  { status: "SAFE", field: "safe" },
];
const deadlinesRows = computed(() => {
  const deadlines = summary.value?.deadlines;
  if (!deadlines) return [];
  return DEADLINE_ROWS.map(({ status, field }) => ({
    key: status,
    label: workNeedStatusLabel(status),
    tone: workNeedStatusTone(status),
    count: deadlines[field] as number,
  }));
});

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

        <div class="info-row">
          <section class="surface info-card">
            <div class="surface-header"><div><h2><CheckCircle2 :size="15" /> Negociação</h2><p>Baseado na data de negociação registrada.</p></div></div>
            <div class="surface-body negotiation-body">
              <div class="negotiation-numbers">
                <div class="detail-field"><span>Concluídas</span><strong>{{ formatNumber(summary.negotiation.completed, 0) }}</strong></div>
                <div class="detail-field"><span>Em aberto</span><strong>{{ formatNumber(summary.negotiation.open, 0) }}</strong></div>
                <div class="detail-field"><span>Em negociação/equalização</span><strong>{{ formatNumber(summary.negotiation.inNegotiation, 0) }}</strong></div>
              </div>
              <UnitProgressBars
                v-if="progress !== null"
                :items="[{ label: 'Negociações concluídas', value: progress }]"
                :target="null"
              />
            </div>
          </section>

          <section class="surface info-card">
            <div class="surface-header"><div><h2><Clock :size="15" /> Situação de prazos</h2><p>Status necessidade da obra (limite de entrega em obra).</p></div></div>
            <div class="surface-body">
              <p v-if="!summary.deadlines.available" class="not-calculated" data-testid="deadlines-unavailable">
                Indicador aguardando definição da regra de prazo.
                <small>{{ summary.deadlines.reason }}</small>
              </p>
              <div v-else class="deadlines-body" data-testid="deadlines-summary">
                <ul class="deadlines-list">
                  <li v-for="row in deadlinesRows" :key="row.key" class="deadlines-row" :class="row.tone">
                    <span>{{ row.label }}</span>
                    <strong>{{ formatNumber(row.count, 0) }}</strong>
                  </li>
                </ul>
                <div class="deadlines-footer">
                  <span>Sem prazo calculável</span>
                  <strong>{{ formatNumber(summary.deadlines.withoutDeadline, 0) }}</strong>
                </div>
              </div>
            </div>
          </section>

          <section class="surface info-card">
            <div class="surface-header"><div><h2><CalendarClock :size="15" /> Próxima startup</h2><p>Menor data futura no recorte.</p></div></div>
            <div class="surface-body startup-body">
              <strong class="startup-date">{{ formatDateOnly(summary.startup.nextAt) }}</strong>
              <span class="startup-detail">{{ startupLabel(summary) }}</span>
              <NuxtLink v-if="summary.startup.equipmentId" class="startup-link" :to="`/equipamentos/${summary.startup.equipmentId}`">
                <Receipt :size="13" /> {{ summary.startup.equipmentName }}
              </NuxtLink>
            </div>
          </section>
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
.info-row { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 18px; align-items: start; }
.surface-header h2 { display: inline-flex; align-items: center; gap: 7px; }
.chart-surface .surface-body { padding: 8px 20px 2px; }
.info-card { min-height: 210px; }
.negotiation-body { display: grid; gap: 16px; }
.negotiation-numbers { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
/* Altura fixa no rótulo mantém os três números alinhados mesmo com label em duas linhas. */
.negotiation-numbers .detail-field { grid-template-rows: 28px auto; }
.detail-field { display: grid; align-content: start; gap: 5px; }
.detail-field > span { color: #7a879a; font-size: 10px; font-weight: 800; letter-spacing: .05em; text-transform: uppercase; }
.detail-field strong { color: #2b3e58; font-size: 18px; font-weight: 750; }
.not-calculated { display: grid; gap: 7px; margin: 0; color: #9b6418; font-size: 12.5px; font-weight: 700; }
.not-calculated small { color: #8b96a5; font-size: 11px; font-weight: 500; }
.deadlines-body { display: grid; gap: 10px; }
.deadlines-list { display: grid; gap: 6px; margin: 0; padding: 0; list-style: none; }
.deadlines-row { display: flex; align-items: center; justify-content: space-between; padding: 5px 9px; border-radius: 8px; font-size: 12.5px; font-weight: 600; border-left: 3px solid transparent; }
.deadlines-row.negotiation-badge--danger { background: #fbe8e8; color: #a53f3f; border-left-color: #c96a6a; }
.deadlines-row.negotiation-badge--warning { background: #fff3df; color: #9b6418; border-left-color: #d3a24d; }
.deadlines-row.negotiation-badge--ok { background: #e8f1fc; color: #2f5f9c; border-left-color: #5c8fc9; }
.deadlines-footer { display: flex; align-items: center; justify-content: space-between; padding: 5px 9px; color: #8b96a5; font-size: 11.5px; font-weight: 600; border-top: 1px solid #edf0f4; padding-top: 8px; }
.startup-body { display: grid; gap: 7px; }
.startup-date { color: #2b3e58; font-size: 22px; font-weight: 750; }
.startup-detail { color: #65748a; font-size: 12.5px; }
.startup-link { display: inline-flex; align-items: center; gap: 6px; color: #304f7e; font-size: 12px; font-weight: 700; text-decoration: none; }
@media (max-width: 1100px) { .chart-row, .info-row { grid-template-columns: 1fr; } }
@media (max-width: 620px) { .negotiation-numbers { grid-template-columns: 1fr; } }
</style>
