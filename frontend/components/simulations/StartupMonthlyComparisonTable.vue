<script setup lang="ts">
import { VBtn, VTable } from "vuetify/components";
import type { StartupMetric, StartupScenario } from "~/types/startupSimulation";
import { buildMonthlyComparisonRows } from "~/utils/startupComparison";
import { formatMonth } from "~/utils/startupSimulation";

const props = defineProps<{
  scenarioA: StartupScenario | null;
  scenarioB: StartupScenario | null;
  activeScenarioId?: string;
  activeMetric?: StartupMetric;
  activeMonth?: string;
}>();
const emit = defineEmits<{
  "select-deadline": [scenarioId: string, metric: StartupMetric, month: string];
}>();
const metrics: Array<{ key: StartupMetric; label: string }> = [
  { key: "negotiations", label: "Negociação" },
  { key: "contracts", label: "Contrato/OC" },
  { key: "deliveries", label: "Entrega na obra" },
];
const rows = computed(() => buildMonthlyComparisonRows(props.scenarioA, props.scenarioB));
const totals = computed(() => Object.fromEntries(metrics.map(({ key }) => [
  key, {
    a: rows.value.reduce((sum, row) => sum + row.a[key], 0),
    b: props.scenarioB ? rows.value.reduce((sum, row) => sum + (row.b?.[key] ?? 0), 0) : null,
  },
])) as Record<StartupMetric, { a: number; b: number | null }>);

function select(scenario: StartupScenario | null, metric: StartupMetric, month: string, count: number): void {
  if (scenario && count > 0) emit("select-deadline", scenario.id, metric, month);
}
function isSelected(scenario: StartupScenario | null, metric: StartupMetric, month: string): boolean {
  return Boolean(scenario && scenario.id === props.activeScenarioId
    && props.activeMetric === metric && props.activeMonth === month);
}
</script>

<template>
  <section class="surface monthly-comparison" aria-labelledby="monthly-comparison-title">
    <header class="comparison-heading">
      <div>
        <h2 id="monthly-comparison-title">Distribuição mensal de prazos</h2>
        <p>Contagem de equipamentos com data-limite em cada mês, por cenário e etapa. Selecione um número para localizar os equipamentos.</p>
      </div>
      <div class="scenario-legend" aria-label="Legenda dos cenários">
        <span><i class="series-dot series-dot--a" aria-hidden="true" /> A: {{ scenarioA?.name ?? "—" }}</span>
        <span><i class="series-dot series-dot--b" aria-hidden="true" /> B: {{ scenarioB?.name ?? "—" }}</span>
      </div>
    </header>
    <div v-if="!rows.length" class="monthly-empty" role="status">
      Nenhuma data-limite calculável para os cenários selecionados.
    </div>
    <div v-else class="monthly-scroll">
      <VTable density="compact" class="monthly-table" aria-label="Prazos mensais dos cenários A e B">
        <thead>
          <tr class="group-head">
            <th scope="col" rowspan="2" class="month-col">Mês</th>
            <th v-for="item in metrics" :key="item.key" scope="colgroup" colspan="2" class="group-title">
              {{ item.label }}
            </th>
          </tr>
          <tr class="subhead">
            <template v-for="item in metrics" :key="item.key">
              <th scope="col" :title="scenarioA?.name ?? ''">
                <i class="series-dot series-dot--a" aria-hidden="true" /> A
              </th>
              <th scope="col" :title="scenarioB?.name ?? ''">
                <i class="series-dot series-dot--b" aria-hidden="true" /> B
              </th>
            </template>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.month">
            <th scope="row" class="month-name">{{ formatMonth(row.month) }}</th>
            <template v-for="item in metrics" :key="item.key">
              <td :class="{ 'selected-deadline': isSelected(scenarioA, item.key, row.month) }">
                <VBtn
                  v-if="row.a[item.key] > 0"
                  variant="text" color="primary" size="x-small" class="count-button"
                  :aria-label="`${row.a[item.key]} equipamentos em ${item.label}, ${formatMonth(row.month)}, ${scenarioA?.name ?? 'cenário A'}. Filtrar tabela`"
                  @click="select(scenarioA, item.key, row.month, row.a[item.key])"
                >{{ row.a[item.key] }}</VBtn>
                <span v-else class="zero-count">0</span>
              </td>
              <td :class="{ 'selected-deadline': isSelected(scenarioB, item.key, row.month) }">
                <VBtn
                  v-if="row.b && row.b[item.key] > 0"
                  variant="text" color="primary" size="x-small" class="count-button"
                  :aria-label="`${row.b[item.key]} equipamentos em ${item.label}, ${formatMonth(row.month)}, ${scenarioB?.name ?? 'cenário B'}. Filtrar tabela`"
                  @click="select(scenarioB, item.key, row.month, row.b[item.key])"
                >{{ row.b[item.key] }}</VBtn>
                <span v-else :class="row.b ? 'zero-count' : 'missing-count'">{{ row.b ? "0" : "—" }}</span>
              </td>
            </template>
          </tr>
        </tbody>
        <tfoot>
          <tr>
            <th scope="row">Total</th>
            <template v-for="item in metrics" :key="item.key">
              <td>{{ totals[item.key].a }}</td>
              <td>{{ totals[item.key].b ?? "—" }}</td>
            </template>
          </tr>
        </tfoot>
      </VTable>
    </div>
    <p class="monthly-footnote">
      Meses sem vencimentos permanecem na comparação. O zero representa nenhum prazo calculado naquele mês;
      “—” indica um cenário não selecionado.
    </p>
  </section>
</template>

<style scoped>
.monthly-comparison { padding: 18px; margin: 16px 0; min-width: 0; }
.comparison-heading { display: flex; gap: 14px; align-items: start; justify-content: space-between; flex-wrap: wrap; margin-bottom: 14px; }
.comparison-heading h2 { color: #213758; font-size: 15px; font-weight: 800; margin: 0; }
.comparison-heading p { font-size: 11.5px; color: #7d8a9d; line-height: 1.5; margin: 4px 0 0; }
.scenario-legend { display: flex; flex-wrap: wrap; gap: 12px; font-size: 11px; color: #67778b; }
.scenario-legend > span { display: flex; align-items: center; gap: 6px; }
.series-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; flex-shrink: 0; }
.series-dot--a { background: #304f7e; }
.series-dot--b { background: #eaa239; }
.monthly-scroll { width: 100%; max-height: 560px; overflow: auto; border: 1px solid #e7ecf3; border-radius: 9px; }
.monthly-table { min-width: 600px; font-size: 11.5px; color: #31435c; font-variant-numeric: tabular-nums; }
.monthly-table :deep(th) { color: #52677f; font-weight: 750; background: #f4f7fb; }
.monthly-table :deep(thead th) { position: sticky; z-index: 2; text-align: center; white-space: nowrap; }
.monthly-table :deep(thead .group-head th) { top: 0; padding: 9px 11px; }
.monthly-table :deep(thead .subhead th) { top: 36px; padding: 6px 11px; background: #f7f9fc; }
.monthly-table :deep(thead .month-col) { text-align: left; z-index: 3; }
.monthly-table :deep(td) { text-align: center; padding: 3px 10px; min-width: 72px; }
.monthly-table :deep(.month-name) { text-align: left; padding: 8px 12px; white-space: nowrap; font-weight: 700; background: #fff; }
.monthly-table :deep(tbody tr:nth-child(even)) { background: #f9fbfd; }
.monthly-table :deep(tbody tr:nth-child(even) .month-name) { background: #f9fbfd; }
.monthly-table :deep(.selected-deadline) { background: #e8eff9; }
.count-button { min-width: 28px; height: 26px; padding: 0 6px; font-size: 11.5px; font-weight: 700; }
.zero-count { color: #9ba6b5; }
.missing-count { color: #b3bdca; }
.monthly-table :deep(tfoot th), .monthly-table :deep(tfoot td) { background: #eef3f9; font-weight: 800; padding: 10px 12px; }
.monthly-table :deep(tfoot td) { text-align: center; }
.monthly-empty { padding: 30px 20px; text-align: center; font-size: 12px; color: #8794a5; background: #fafbfd; border: 1px dashed #e7ecf3; border-radius: 9px; }
.monthly-footnote { margin: 10px 0 0; font-size: 10.5px; color: #8593a6; line-height: 1.6; }
@media (max-width: 700px) { .monthly-comparison { padding: 14px; } }
</style>
