<script setup lang="ts">
import { VTable } from "vuetify/components";
import type { StartupScenario } from "~/types/startupSimulation";
import {
  comparisonDateDelta, comparisonNumberDelta, formatAverageDays, formatDaysDifference,
} from "~/utils/startupComparison";
import { formatScenarioDate } from "~/utils/startupSimulation";

const props = defineProps<{
  scenarioA: StartupScenario | null;
  scenarioB: StartupScenario | null;
  draftScenarioId?: string | null;
}>();

const numberOfEquipments = computed(() => {
  if (!props.scenarioA) return "—";
  if (!props.scenarioB || props.scenarioA.summary.equipments === props.scenarioB.summary.equipments) {
    return String(props.scenarioA.summary.equipments);
  }
  return `${props.scenarioA.summary.equipments} / ${props.scenarioB.summary.equipments}`;
});

const equipmentDetail = computed(() => {
  if (!props.scenarioB) return "Cenário A";
  return props.scenarioA?.summary.equipments === props.scenarioB.summary.equipments
    ? "Em cada cenário" : "A / B — quantidades diferentes";
});

const difference = computed(() =>
  formatDaysDifference(comparisonDateDelta(props.scenarioA?.startupAt, props.scenarioB?.startupAt)),
);

type Indicator = { key: string; label: string; a: string; b: string; delta: string };
const indicators = computed<Indicator[]>(() => {
  const a = props.scenarioA?.summary;
  const b = props.scenarioB?.summary;
  const dateRow = (
    key: string, label: string,
    field: "firstNegotiation" | "lastNegotiation" | "firstDelivery" | "lastDelivery",
  ): Indicator => ({
    key, label,
    a: formatScenarioDate(a?.[field] ?? null),
    b: formatScenarioDate(b?.[field] ?? null),
    delta: formatDaysDifference(comparisonDateDelta(a?.[field], b?.[field])),
  });
  const averageRow = (
    key: string, label: string, field: "averageManufactureDays" | "averagePreStartDays",
  ): Indicator => ({
    key, label,
    a: formatAverageDays(a?.[field]),
    b: formatAverageDays(b?.[field]),
    delta: formatDaysDifference(comparisonNumberDelta(a?.[field], b?.[field]), 1),
  });
  return [
    dateRow("first-negotiation", "Primeira negociação", "firstNegotiation"),
    dateRow("last-negotiation", "Última negociação", "lastNegotiation"),
    dateRow("first-delivery", "Primeira entrega", "firstDelivery"),
    dateRow("last-delivery", "Última entrega", "lastDelivery"),
    averageRow("manufacture", "Lead time de fabricação médio", "averageManufactureDays"),
    averageRow("pre-start", "Dias antes do startup médio", "averagePreStartDays"),
  ];
});
</script>

<template>
  <section class="startup-comparison" aria-labelledby="startup-comparison-title">
    <header class="comparison-header">
      <div>
        <h2 id="startup-comparison-title">Visão executiva · cenários de startup</h2>
        <p>Comparativo direto dos cenários selecionados. Diferença = B − A, em dias corridos.</p>
      </div>
      <span v-if="draftScenarioId && [scenarioA?.id, scenarioB?.id].includes(draftScenarioId)" class="draft-flag">
        Alterações não salvas refletidas nos valores
      </span>
    </header>

    <div class="overview-grid">
      <article class="overview-card">
        <span class="card-label">Equipamentos</span>
        <strong class="card-value" data-testid="simulation-equipment-count">{{ numberOfEquipments }}</strong>
        <span class="card-detail">{{ equipmentDetail }}</span>
      </article>
      <article class="overview-card">
        <span class="card-label"><i class="series-dot series-dot--a" aria-hidden="true" /> Startup · Cenário A</span>
        <strong class="card-value card-value--date">{{ formatScenarioDate(scenarioA?.startupAt ?? null) }}</strong>
        <span class="card-detail" :title="scenarioA?.name ?? ''">{{ scenarioA?.name ?? "Selecione um cenário" }}</span>
      </article>
      <article class="overview-card">
        <span class="card-label"><i class="series-dot series-dot--b" aria-hidden="true" /> Startup · Cenário B</span>
        <strong class="card-value card-value--date">{{ formatScenarioDate(scenarioB?.startupAt ?? null) }}</strong>
        <span class="card-detail" :title="scenarioB?.name ?? ''">{{ scenarioB?.name ?? "Selecione o cenário B" }}</span>
      </article>
      <article class="overview-card">
        <span class="card-label">Deslocamento do startup</span>
        <strong class="card-value" data-testid="simulation-startup-shift">{{ difference }}</strong>
        <span class="card-detail">Cenário B em relação ao A</span>
      </article>
    </div>

    <div class="surface indicators-panel">
      <header class="indicators-header">
        <h3>Indicadores comparativos</h3>
        <p>Datas-limite e prazos médios calculados para cada cenário.</p>
      </header>
      <div class="indicators-scroll">
        <VTable density="compact" class="indicators-table">
          <thead>
            <tr>
              <th scope="col">Indicador</th>
              <th scope="col" class="numeric">
                <span class="column-heading"><i class="series-dot series-dot--a" aria-hidden="true" /> Cenário A</span>
                <small :title="scenarioA?.name ?? ''">{{ scenarioA?.name ?? "—" }}</small>
              </th>
              <th scope="col" class="numeric">
                <span class="column-heading"><i class="series-dot series-dot--b" aria-hidden="true" /> Cenário B</span>
                <small :title="scenarioB?.name ?? ''">{{ scenarioB?.name ?? "—" }}</small>
              </th>
              <th scope="col" class="numeric">Diferença (B − A)</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in indicators" :key="item.key">
              <th scope="row">{{ item.label }}</th>
              <td class="numeric">{{ item.a }}</td>
              <td class="numeric">{{ item.b }}</td>
              <td class="numeric delta-value" :class="{ 'delta-empty': item.delta === '—' }">{{ item.delta }}</td>
            </tr>
          </tbody>
        </VTable>
      </div>
      <p v-if="!scenarioB" class="comparison-note" role="status">
        Selecione um segundo cenário para ver as diferenças. Os indicadores do cenário A permanecem disponíveis.
      </p>
    </div>
  </section>
</template>

<style scoped>
.startup-comparison { display: grid; gap: 14px; margin-bottom: 16px; min-width: 0; }
.comparison-header { display: flex; justify-content: space-between; align-items: start; flex-wrap: wrap; gap: 12px; }
.comparison-header h2, .indicators-header h3 { color: #213758; font-size: 15px; font-weight: 800; margin: 0; }
.comparison-header p, .indicators-header p { color: #7d8a9d; font-size: 11.5px; margin: 4px 0 0; line-height: 1.5; }
.draft-flag { font-size: 11px; color: #8b620e; background: #fff7e6; border: 1px solid #f5e2b9; padding: 6px 10px; border-radius: 7px; }
.overview-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.overview-card { background: #fff; border: 1px solid #e7ecf3; border-radius: 11px; padding: 17px 18px; display: flex; flex-direction: column; gap: 6px; min-width: 0; }
.card-label { color: #748399; font-size: 11px; font-weight: 650; display: flex; align-items: center; gap: 7px; }
.card-value { font-size: 23px; line-height: 1.4; font-weight: 800; color: #213758; font-variant-numeric: tabular-nums; overflow-wrap: anywhere; }
.card-value--date { font-size: 20px; }
.card-detail { font-size: 11px; color: #929eae; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.series-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; flex-shrink: 0; }
.series-dot--a { background: #304f7e; }
.series-dot--b { background: #eaa239; }
.indicators-panel { padding: 16px 18px 12px; min-width: 0; }
.indicators-header { margin-bottom: 13px; }
.indicators-scroll { overflow-x: auto; border: 1px solid #e8edf4; border-radius: 9px; }
.indicators-table { min-width: 600px; font-size: 12px; color: #31435c; }
.indicators-table :deep(thead th) { background: #f5f8fc; color: #52677f; font-weight: 750; padding: 10px 13px; white-space: nowrap; }
.indicators-table :deep(tbody th) { padding: 10px 13px; font-size: 12px; color: #31435c; text-align: left; font-weight: 600; }
.indicators-table :deep(tbody td) { padding: 10px 13px; }
.indicators-table :deep(.numeric) { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
.column-heading { display: flex; justify-content: flex-end; align-items: center; gap: 6px; }
.indicators-table :deep(thead small) { display: block; font-size: 10px; font-weight: 500; color: #8290a5; max-width: 160px; overflow: hidden; text-overflow: ellipsis; margin-left: auto; }
.delta-value { font-weight: 750; color: #304f7e; }
.delta-empty { color: #98a3b2; font-weight: 400; }
.comparison-note { margin: 12px 3px 0; color: #8390a2; font-size: 11.5px; }
@media (max-width: 1080px) { .overview-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 570px) { .overview-grid { grid-template-columns: 1fr; } .overview-card { padding: 13px 15px; } }
</style>
