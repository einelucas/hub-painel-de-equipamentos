<script setup lang="ts">
import {
  Building2,
  CalendarClock,
  ChevronRight,
  Eye,
  Layers3,
  MapPin,
  UserRound,
  Wrench,
} from "lucide-vue-next";

import type { Equipment, EquipmentList } from "~/types/equipment";
import { formatDateOnly } from "~/utils/format";
import { EQUIPMENT_STAGES } from "~/utils/stages";
import { OPERATIONAL_STATUS_LABELS } from "~/utils/workflow";

/**
 * Kanban somente leitura.
 *
 * Nenhuma ação desta página altera current_stage, operational_status
 * ou qualquer outro dado do equipamento. A navegação abre o detalhe
 * do equipamento, e qualquer transição continua sendo feita pelo fluxo
 * oficial do processo.
 */
definePageMeta({ middleware: "auth" });

const auth = useAuthStore();
const api = useApi();
const context = useModuleContextStore();
const route = useRoute();

const equipments = ref<Equipment[]>([]);
const loading = ref(true);
const error = ref("");

const allowed = computed(() => auth.can("equipments:read"));

type ColumnKey = number | "STANDBY" | "CANCELLED" | "IN_SANITATION";

type ColumnTone =
  | "slate"
  | "cyan"
  | "amber"
  | "violet"
  | "purple"
  | "indigo"
  | "teal"
  | "blue"
  | "green"
  | "neutral"
  | "red"
  | "orange";

interface KanbanColumn {
  key: ColumnKey;
  stage: string | null;
  label: string;
  tone: ColumnTone;
}

const STAGE_TONES: ColumnTone[] = [
  "slate",
  "cyan",
  "amber",
  "violet",
  "purple",
  "indigo",
  "teal",
  "blue",
  "green",
];

const columns = computed<KanbanColumn[]>(() => [
  ...EQUIPMENT_STAGES.map((label, index) => ({
    key: index as ColumnKey,
    stage: String(index),
    label,
    tone: STAGE_TONES[index] ?? "slate",
  })),
  {
    key: "STANDBY",
    stage: null,
    label: "Standby",
    tone: "neutral",
  },
  {
    key: "CANCELLED",
    stage: null,
    label: "Cancelado",
    tone: "red",
  },
  {
    key: "IN_SANITATION",
    stage: null,
    label: "Em Saneamento",
    tone: "orange",
  },
]);

/**
 * Estados operacionais especiais permanecem em suas próprias colunas.
 * ACTIVE usa a etapa normal do workflow.
 */
function columnFor(item: Equipment): ColumnKey {
  if (item.operationalStatus === "ACTIVE") {
    return item.currentStage;
  }

  return item.operationalStatus;
}

const grouped = computed<Map<ColumnKey, Equipment[]>>(() => {
  const map = new Map<ColumnKey, Equipment[]>();

  for (const column of columns.value) {
    map.set(column.key, []);
  }

  for (const item of equipments.value) {
    const key = columnFor(item);
    map.get(key)?.push(item);
  }

  return map;
});

const totalEquipment = computed(() => equipments.value.length);

const occupiedColumns = computed(
  () =>
    columns.value.filter(
      (column) => (grouped.value.get(column.key)?.length ?? 0) > 0,
    ).length,
);

function itemsFor(key: ColumnKey): Equipment[] {
  return grouped.value.get(key) ?? [];
}

function countFor(key: ColumnKey): number {
  return grouped.value.get(key)?.length ?? 0;
}

const PAGE_SIZE = 100;
const PAGE_LIMIT = 20;

async function load(): Promise<void> {
  loading.value = true;
  error.value = "";

  try {
    const rows: Equipment[] = [];

    let page = 1;
    let totalPages = 1;

    do {
      const result = await api.get<EquipmentList>("/equipments", {
        ...context.apiQuery,
        page,
        pageSize: PAGE_SIZE,
        sortBy: "name",
      });

      rows.push(...result.items);

      totalPages = result.pagination.totalPages;
      page += 1;
    } while (page <= totalPages && page <= PAGE_LIMIT);

    equipments.value = rows;
  } catch (caught) {
    error.value =
      caught instanceof Error
        ? caught.message
        : "Não foi possível carregar os equipamentos.";

    equipments.value = [];
  } finally {
    loading.value = false;
  }
}

onMounted(async () => {
  if (!allowed.value) {
    loading.value = false;
    return;
  }

  await context.initialize({
    unit: typeof route.query.unit === "string" ? route.query.unit : undefined,
    equipment:
      typeof route.query.equipment === "string"
        ? route.query.equipment
        : undefined,
  });

  await load();
});
</script>

<template>
  <ModuleWorkspace
    eyebrow="Planejamento · Equipamentos"
    title="Kanban"
    description="Visualização do processo por fase e estado operacional — só leitura, nenhuma ação aqui altera o equipamento."
  >
    <div v-if="!allowed" class="surface empty-state state-card" role="alert">
      <h2>Sem permissão</h2>
      <p>Seu perfil não tem acesso à leitura de equipamentos.</p>
    </div>

    <div v-else class="stack">
      <ModuleFilters :refreshing="loading" @change="load" />

      <div v-if="loading" class="queue-state">
        <span class="spinner" />
        Carregando equipamentos...
      </div>

      <div
        v-else-if="error"
        class="surface empty-state table-empty"
        role="alert"
      >
        <h2>Não foi possível carregar</h2>
        <p>{{ error }}</p>

        <button class="btn" @click="load">Tentar novamente</button>
      </div>

      <template v-else>
        <div class="kanban-summary">
          <div class="summary-main">
            <span class="summary-icon">
              <Layers3 :size="16" />
            </span>

            <div>
              <strong>
                {{ totalEquipment }}
                {{ totalEquipment === 1 ? "equipamento" : "equipamentos" }}
              </strong>

              <span>
                Distribuídos em {{ occupiedColumns }}
                {{ occupiedColumns === 1 ? "coluna ativa" : "colunas ativas" }}
              </span>
            </div>
          </div>

          <div class="read-only-badge">
            <Eye :size="14" />
            Somente leitura
          </div>
        </div>

        <div class="kanban-scroll" data-testid="kanban-board">
          <div class="kanban-board">
            <section
              v-for="column in columns"
              :key="String(column.key)"
              class="kanban-column"
              :class="`kanban-tone--${column.tone}`"
              :data-testid="`kanban-column-${column.key}`"
            >
              <header class="kanban-column-header">
                <div class="column-heading">
                  <span v-if="column.stage !== null" class="column-stage">
                    {{ column.stage }}
                  </span>

                  <h3>{{ column.label }}</h3>
                </div>

                <span class="kanban-count">
                  {{ countFor(column.key) }}
                </span>
              </header>

              <div class="column-accent" />

              <div
                class="kanban-cards"
                :class="{
                  'kanban-cards--empty': !itemsFor(column.key).length,
                }"
              >
                <div v-if="!itemsFor(column.key).length" class="kanban-empty">
                  <span class="empty-dot" />
                  <span>Nenhum equipamento</span>
                </div>

                <NuxtLink
                  v-for="item in itemsFor(column.key)"
                  :key="item.id"
                  :to="`/equipamentos/${item.id}`"
                  class="kanban-card"
                  :data-testid="`kanban-card-${item.id}`"
                >
                  <div class="card-header">
                    <strong class="card-title">
                      {{ item.name }}
                    </strong>

                    <ChevronRight :size="15" class="card-arrow" />
                  </div>

                  <div class="card-context">
                    <span class="context-chip">
                      <Building2 :size="12" />
                      {{ item.unit.code }}
                    </span>

                    <span class="context-separator" />

                    <span>
                      {{ item.projectContext.code }}
                    </span>
                  </div>

                  <div v-if="item.discipline || item.area" class="card-meta-row">
                    <span v-if="item.discipline" class="meta-chip">
                      <Wrench :size="11" />
                      {{ item.discipline.name }}
                    </span>
                    <span v-if="item.area" class="meta-chip">
                      <MapPin :size="11" />
                      {{ item.area.name }}
                    </span>
                  </div>

                  <div v-if="item.calculated.deliveryDeadline" class="card-meta-row">
                    <span class="meta-chip">
                      <CalendarClock :size="11" />
                      Limite entrega em obra: {{ formatDateOnly(item.calculated.deliveryDeadline) }}
                    </span>
                  </div>

                  <div class="card-footer">
                    <div class="card-responsible">
                      <span class="responsible-avatar">
                        <UserRound :size="12" />
                      </span>

                      <span>
                        {{ item.responsibleUser?.name ?? "Sem responsável" }}
                      </span>
                    </div>

                    <span
                      v-if="item.operationalStatus !== 'ACTIVE'"
                      class="kanban-status-badge"
                    >
                      {{ OPERATIONAL_STATUS_LABELS[item.operationalStatus] }}
                    </span>
                  </div>
                </NuxtLink>
              </div>
            </section>
          </div>
        </div>
      </template>
    </div>
  </ModuleWorkspace>
</template>

<style scoped>
.state-card {
  max-width: none;
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
  padding: 28px;
}

/* =========================================================
   SUMMARY
   ========================================================= */

.kanban-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;

  padding: 12px 15px;

  border: 1px solid #e0e6ee;
  border-radius: 11px;

  background: #ffffff;

  box-shadow: 0 5px 18px rgb(35 55 80 / 4%);
}

.summary-main {
  display: flex;
  align-items: center;
  gap: 10px;
}

.summary-icon {
  display: grid;
  width: 32px;
  height: 32px;
  flex: 0 0 32px;
  place-items: center;

  border-radius: 8px;

  background: #edf2f8;
  color: #304f7e;
}

.summary-main > div {
  display: grid;
  gap: 1px;
}

.summary-main strong {
  color: #2b3e58;

  font-size: 11.5px;
  font-weight: 750;
}

.summary-main span {
  color: #8793a4;

  font-size: 10px;
}

.read-only-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;

  padding: 5px 9px;

  border: 1px solid #dbe3ed;
  border-radius: 999px;

  background: #f7f9fc;
  color: #66758a;

  font-size: 9.5px;
  font-weight: 700;
}

/* =========================================================
   BOARD / SCROLL
   ========================================================= */

.kanban-scroll {
  width: 100%;
  overflow-x: auto;
  overflow-y: hidden;

  padding: 1px 1px 10px;

  scrollbar-width: thin;
  scrollbar-color: #aab3bf #edf1f5;
}

.kanban-scroll::-webkit-scrollbar {
  height: 9px;
}

.kanban-scroll::-webkit-scrollbar-track {
  border-radius: 999px;
  background: #edf1f5;
}

.kanban-scroll::-webkit-scrollbar-thumb {
  border: 2px solid #edf1f5;
  border-radius: 999px;
  background: #aab3bf;
}

.kanban-board {
  display: flex;
  width: max-content;
  min-width: 100%;
  align-items: stretch;
  gap: 12px;
}

/* =========================================================
   COLUMN
   ========================================================= */

.kanban-column {
  --column-accent: #7890ad;
  --column-soft: #eef2f7;
  --column-text: #40556f;

  position: relative;

  display: flex;
  width: 286px;
  min-width: 286px;
  height: clamp(500px, calc(100vh - 330px), 720px);
  flex-direction: column;

  overflow: hidden;

  border: 1px solid #dfe5ed;
  border-radius: 11px;

  background: #f4f6f9;

  box-shadow: 0 4px 14px rgb(31 49 73 / 3%);
}

.kanban-column-header {
  position: sticky;
  top: 0;
  z-index: 3;

  display: flex;
  min-height: 48px;
  align-items: center;
  justify-content: space-between;
  gap: 10px;

  padding: 0 12px;

  background: #ffffff;
}

.column-accent {
  width: 100%;
  height: 4px;
  flex: 0 0 4px;

  background: var(--column-accent);
}

.column-heading {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 7px;
}

.column-stage {
  display: grid;
  width: 22px;
  height: 22px;
  flex: 0 0 22px;
  place-items: center;

  border-radius: 6px;

  background: var(--column-soft);
  color: var(--column-text);

  font-size: 9px;
  font-weight: 800;
}

.kanban-column-header h3 {
  overflow: hidden;

  margin: 0;

  color: #243953;

  font-size: 11.5px;
  font-weight: 780;
  line-height: 1.25;

  text-overflow: ellipsis;
  white-space: nowrap;
}

.kanban-count {
  display: inline-flex;
  min-width: 24px;
  min-height: 24px;
  align-items: center;
  justify-content: center;

  padding: 2px 7px;

  border: 1px solid #e0e6ee;
  border-radius: 999px;

  background: #f8fafc;
  color: #6f7e91;

  font-size: 9.5px;
  font-weight: 760;
}

/* =========================================================
   CARDS AREA
   ========================================================= */

.kanban-cards {
  display: grid;
  align-content: start;
  gap: 9px;

  min-height: 0;
  flex: 1;

  overflow-y: auto;

  padding: 10px;

  scrollbar-width: thin;
  scrollbar-color: #aeb7c2 transparent;
}

.kanban-cards::-webkit-scrollbar {
  width: 7px;
}

.kanban-cards::-webkit-scrollbar-track {
  background: transparent;
}

.kanban-cards::-webkit-scrollbar-thumb {
  border: 2px solid transparent;
  border-radius: 999px;

  background: #aeb7c2;
  background-clip: content-box;
}

.kanban-cards--empty {
  display: flex;
  align-items: flex-start;
  justify-content: center;
}

.kanban-empty {
  display: inline-flex;
  align-items: center;
  gap: 7px;

  margin-top: 12px;
  padding: 7px 9px;

  border-radius: 7px;

  color: #9aa5b4;

  font-size: 10px;
  font-weight: 500;
}

.empty-dot {
  width: 6px;
  height: 6px;

  border-radius: 50%;

  background: #c8d0da;
}

/* =========================================================
   CARD
   ========================================================= */

.kanban-card {
  display: grid;
  gap: 11px;

  padding: 12px;

  border: 1px solid #dde4ec;
  border-radius: 10px;

  background: #ffffff;
  color: inherit;

  text-decoration: none;

  box-shadow: 0 3px 9px rgb(31 48 70 / 3%);

  transition:
    border-color 0.15s ease,
    box-shadow 0.15s ease,
    transform 0.15s ease;
}

.kanban-card:hover {
  border-color: #bcc9d8;

  box-shadow: 0 7px 18px rgb(31 48 70 / 8%);

  transform: translateY(-1px);
}

.card-header {
  display: flex;
  min-width: 0;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
}

.card-title {
  display: -webkit-box;
  overflow: hidden;

  color: #243953;

  font-size: 12.5px;
  font-weight: 750;
  line-height: 1.4;

  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
}

.card-arrow {
  flex: 0 0 auto;

  margin-top: 1px;

  color: #a1adbc;

  transition:
    color 0.15s ease,
    transform 0.15s ease;
}

.kanban-card:hover .card-arrow {
  color: #304f7e;

  transform: translateX(2px);
}

.card-context {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 7px;

  color: #77869a;

  font-size: 10px;
  font-weight: 550;
}

.context-chip {
  display: inline-flex;
  min-width: 0;
  align-items: center;
  gap: 5px;

  color: #536b88;
}

.context-separator {
  width: 3px;
  height: 3px;
  flex: 0 0 3px;

  border-radius: 50%;

  background: #b8c2cf;
}

.card-meta-row {
  display: flex;
  flex-wrap: wrap;
  min-width: 0;
  align-items: center;
  gap: 6px;

  margin-top: 6px;
}

.meta-chip {
  display: inline-flex;
  min-width: 0;
  align-items: center;
  gap: 4px;

  color: #77869a;

  font-size: 10px;
  font-weight: 550;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.card-footer {
  display: flex;
  min-width: 0;
  align-items: center;
  justify-content: space-between;
  gap: 8px;

  padding-top: 9px;

  border-top: 1px solid #eef1f5;
}

.card-responsible {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 7px;

  color: #758397;

  font-size: 10px;
}

.card-responsible > span:last-child {
  overflow: hidden;

  text-overflow: ellipsis;
  white-space: nowrap;
}

.responsible-avatar {
  display: grid;
  width: 22px;
  height: 22px;
  flex: 0 0 22px;
  place-items: center;

  border-radius: 50%;

  background: #edf2f8;
  color: #4d6888;
}

.kanban-status-badge {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;

  padding: 3px 7px;

  border: 1px solid #ead9bd;
  border-radius: 999px;

  background: #fff8eb;
  color: #98621e;

  font-size: 8.5px;
  font-weight: 750;
}

/* =========================================================
   COLUMN TONES
   ========================================================= */

.kanban-tone--slate {
  --column-accent: #8794aa;
  --column-soft: #eef1f5;
  --column-text: #59667b;
}

.kanban-tone--cyan {
  --column-accent: #4f9bbd;
  --column-soft: #e9f5fa;
  --column-text: #367d9b;
}

.kanban-tone--amber {
  --column-accent: #dfa64c;
  --column-soft: #fff4df;
  --column-text: #96651c;
}

.kanban-tone--violet {
  --column-accent: #9270c7;
  --column-soft: #f1ebfa;
  --column-text: #70529e;
}

.kanban-tone--purple {
  --column-accent: #7166b5;
  --column-soft: #eeecfa;
  --column-text: #595099;
}

.kanban-tone--indigo {
  --column-accent: #607eb5;
  --column-soft: #ebf0f8;
  --column-text: #486493;
}

.kanban-tone--teal {
  --column-accent: #4e9a8f;
  --column-soft: #e9f5f2;
  --column-text: #377c72;
}

.kanban-tone--blue {
  --column-accent: #4e80bb;
  --column-soft: #eaf1f9;
  --column-text: #38689e;
}

.kanban-tone--green {
  --column-accent: #5d9560;
  --column-soft: #edf6ed;
  --column-text: #47794a;
}

.kanban-tone--neutral {
  --column-accent: #8993a2;
  --column-soft: #f0f2f5;
  --column-text: #626d7b;
}

.kanban-tone--red {
  --column-accent: #c56f69;
  --column-soft: #fbeceb;
  --column-text: #9e4f4a;
}

.kanban-tone--orange {
  --column-accent: #cb8951;
  --column-soft: #fff0e4;
  --column-text: #986035;
}

/* =========================================================
   RESPONSIVE
   ========================================================= */

@media (max-width: 900px) {
  .kanban-column {
    width: 260px;
    min-width: 260px;
  }
}

@media (max-width: 700px) {
  .kanban-summary {
    align-items: flex-start;
    flex-direction: column;
  }

  .kanban-column {
    width: 238px;
    min-width: 238px;
    height: 62vh;
  }
}
</style>
