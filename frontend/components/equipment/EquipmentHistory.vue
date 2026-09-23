<script setup lang="ts">
import { computed, ref } from "vue";
import {
  Activity,
  ArrowRightLeft,
  Clock3,
  FileText,
  History,
  RefreshCcw,
  ShieldCheck,
  UserRound,
} from "lucide-vue-next";

import type { HistoryEntry, HistoryList } from "~/types/equipment";
import { formatDateTime } from "~/utils/format";

/**
 * Histórico do equipamento.
 *
 * Componente somente leitura e autocontido:
 * busca os dados a partir de equipmentId e mantém estados próprios
 * de loading, erro e vazio.
 */
const props = defineProps<{
  equipmentId: string;
}>();

const api = useApi();

const entries = ref<HistoryEntry[]>([]);
const loading = ref(true);
const error = ref("");

const entryCountLabel = computed(() => {
  const count = entries.value.length;

  return `${count} ${count === 1 ? "registro" : "registros"}`;
});

function kindLabel(kind: HistoryEntry["kind"]): string {
  if (kind === "change") {
    return "Alteração";
  }

  if (kind === "operational_status") {
    return "Estado operacional";
  }

  return "Processo";
}

function kindIcon(kind: HistoryEntry["kind"]) {
  if (kind === "change") {
    return RefreshCcw;
  }

  if (kind === "operational_status") {
    return ShieldCheck;
  }

  return ArrowRightLeft;
}

function kindClass(kind: HistoryEntry["kind"]): string {
  if (kind === "change") {
    return "event--change";
  }

  if (kind === "operational_status") {
    return "event--status";
  }

  return "event--process";
}

/**
 * Apenas melhora a apresentação de chaves técnicas cruas.
 * Títulos descritivos vindos do backend permanecem intocados.
 */
function displayTitle(title: string): string {
  const normalized = title.trim();

  if (!/^[a-z0-9_.-]+$/i.test(normalized)) {
    return normalized;
  }

  const readable = normalized
    .replace(/[._-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();

  return readable.charAt(0).toUpperCase() + readable.slice(1);
}

async function load(): Promise<void> {
  loading.value = true;
  error.value = "";

  try {
    entries.value = (
      await api.get<HistoryList>(`/equipments/${props.equipmentId}/history`)
    ).items;
  } catch (caught) {
    error.value =
      caught instanceof Error
        ? caught.message
        : "Não foi possível carregar o histórico.";
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<template>
  <section class="history-panel">
    <header class="history-header">
      <div class="history-heading">
        <div class="history-heading-icon">
          <History :size="18" />
        </div>

        <div class="history-heading-copy">
          <div class="history-title-row">
            <h2>Histórico</h2>

            <span v-if="!loading" class="history-count">
              {{ entryCountLabel }}
            </span>
          </div>

          <p>
            Transições de etapa, estados especiais e alterações relevantes do
            processo.
          </p>
        </div>
      </div>

      <span class="read-only-badge"> Somente leitura </span>
    </header>

    <div v-if="loading" class="history-state" data-testid="history-loading">
      <span class="spinner" />
      Carregando histórico...
    </div>

    <div v-else-if="error" class="history-error" role="alert">
      <span class="state-icon">
        <History :size="22" />
      </span>

      <div class="state-copy">
        <strong>Não foi possível carregar</strong>
        <p>{{ error }}</p>
      </div>

      <button type="button" class="retry-button" @click="load">
        Tentar novamente
      </button>
    </div>

    <div
      v-else-if="entries.length === 0"
      class="history-empty"
      data-testid="history-empty"
    >
      <span class="state-icon">
        <History :size="22" />
      </span>

      <div class="state-copy">
        <strong>Sem registros</strong>
        <p>As ações realizadas neste equipamento aparecerão aqui.</p>
      </div>
    </div>

    <div v-else class="timeline" data-testid="history-timeline">
      <article
        v-for="entry in entries"
        :key="entry.id"
        class="timeline-event"
        :class="kindClass(entry.kind)"
        :data-testid="`history-${entry.id}`"
      >
        <div class="timeline-rail" aria-hidden="true">
          <span class="timeline-node">
            <component :is="kindIcon(entry.kind)" :size="13" />
          </span>

          <span class="timeline-line" />
        </div>

        <div class="event-card">
          <div class="event-header">
            <div class="event-heading">
              <span class="event-type">
                {{ kindLabel(entry.kind) }}
              </span>

              <h3>
                {{ displayTitle(entry.title) }}
              </h3>
            </div>

            <div class="event-time">
              <Clock3 :size="12" />
              {{ formatDateTime(entry.occurredAt) }}
            </div>
          </div>

          <div v-if="entry.reason || entry.justification" class="event-details">
            <div v-if="entry.reason" class="detail-row">
              <FileText :size="13" />

              <div>
                <span>Motivo</span>
                <p>{{ entry.reason }}</p>
              </div>
            </div>

            <div
              v-if="entry.justification"
              class="detail-row detail-row--justification"
            >
              <Activity :size="13" />

              <div>
                <span>Justificativa</span>
                <p>{{ entry.justification }}</p>
              </div>
            </div>
          </div>

          <footer class="event-footer">
            <div class="event-actor">
              <span class="actor-icon">
                <UserRound :size="12" />
              </span>

              <span>
                {{ entry.actor?.name ?? "Usuário removido" }}
              </span>
            </div>
          </footer>
        </div>
      </article>
    </div>
  </section>
</template>

<style scoped>
.history-panel {
  overflow: hidden;

  border: 1px solid #dde4ed;
  border-radius: 16px;

  background: #ffffff;

  box-shadow: 0 12px 28px rgb(29 48 76 / 5%);
}

/* =========================================================
   HEADER
   ========================================================= */

.history-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;

  padding: 20px 24px;

  border-bottom: 1px solid #edf1f5;
}

.history-heading {
  display: flex;
  min-width: 0;
  align-items: flex-start;
  gap: 12px;
}

.history-heading-icon {
  display: grid;
  width: 36px;
  height: 36px;
  flex: 0 0 36px;
  place-items: center;

  border-radius: 10px;

  background: #edf2f8;
  color: #304f7e;
}

.history-heading-copy {
  min-width: 0;
}

.history-title-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 9px;
}

.history-title-row h2 {
  margin: 0;

  color: #18375c;

  font-size: 18px;
  font-weight: 760;
  line-height: 1.2;
}

.history-count {
  display: inline-flex;
  min-height: 22px;
  align-items: center;

  padding: 2px 9px;

  border: 1px solid #dce4ed;
  border-radius: 999px;

  background: #f6f8fb;
  color: #718097;

  font-size: 10px;
  font-weight: 700;
}

.history-heading-copy p {
  margin: 6px 0 0;

  color: #7e899c;

  font-size: 12px;
  line-height: 1.45;
}

.read-only-badge {
  display: inline-flex;
  min-height: 25px;
  flex: 0 0 auto;
  align-items: center;

  padding: 3px 10px;

  border: 1px solid #e2e7ee;
  border-radius: 999px;

  background: #f7f9fb;
  color: #8995a5;

  font-size: 9.5px;
  font-weight: 700;
}

/* =========================================================
   TIMELINE
   ========================================================= */

.timeline {
  padding: 18px 24px 22px;
}

.timeline-event {
  --event-color: #5277a7;
  --event-soft: #edf3fa;

  display: grid;
  grid-template-columns: 34px minmax(0, 1fr);
  gap: 12px;

  min-width: 0;
}

.timeline-event + .timeline-event {
  margin-top: 4px;
}

.timeline-event:last-child .timeline-line {
  display: none;
}

/* Tipos */

.event--process {
  --event-color: #456e9e;
  --event-soft: #edf3fa;
}

.event--change {
  --event-color: #7b8798;
  --event-soft: #f1f3f6;
}

.event--status {
  --event-color: #b47b2c;
  --event-soft: #fff4e2;
}

/* Rail */

.timeline-rail {
  display: flex;
  min-height: 100%;
  align-items: center;
  flex-direction: column;
}

.timeline-node {
  position: relative;
  z-index: 2;

  display: grid;
  width: 28px;
  height: 28px;
  flex: 0 0 28px;
  place-items: center;

  border: 1px solid color-mix(in srgb, var(--event-color) 28%, white);
  border-radius: 50%;

  background: var(--event-soft);
  color: var(--event-color);
}

.timeline-line {
  width: 1px;
  min-height: 26px;
  flex: 1;

  margin: 5px 0;

  background: #e3e8ef;
}

/* Event card */

.event-card {
  min-width: 0;

  margin-bottom: 12px;
  padding: 13px 14px 11px;

  border: 1px solid #e4e9ef;
  border-radius: 10px;

  background: #ffffff;

  transition:
    border-color 0.15s ease,
    box-shadow 0.15s ease,
    transform 0.15s ease;
}

.event-card:hover {
  border-color: #cfd8e4;

  box-shadow: 0 6px 16px rgb(29 48 76 / 6%);

  transform: translateY(-1px);
}

.event-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
}

.event-heading {
  min-width: 0;
}

.event-type {
  display: inline-flex;
  align-items: center;

  margin-bottom: 4px;
  padding: 2px 7px;

  border-radius: 999px;

  background: var(--event-soft);
  color: var(--event-color);

  font-size: 8.5px;
  font-weight: 800;

  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.event-heading h3 {
  margin: 0;

  color: #263e5c;

  font-size: 12.5px;
  font-weight: 750;
  line-height: 1.4;
}

.event-time {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 5px;

  padding-top: 2px;

  color: #94a0b0;

  font-size: 9.5px;
  font-weight: 500;
  white-space: nowrap;
}

/* Details */

.event-details {
  display: grid;
  gap: 7px;

  margin-top: 10px;
  padding: 9px 10px;

  border: 1px solid #edf0f4;
  border-radius: 8px;

  background: #fafbfd;
}

.detail-row {
  display: grid;
  grid-template-columns: 16px minmax(0, 1fr);
  gap: 7px;

  min-width: 0;

  color: #78879b;
}

.detail-row > svg {
  margin-top: 2px;
}

.detail-row > div {
  min-width: 0;
}

.detail-row span {
  display: block;

  margin-bottom: 2px;

  color: #98a2b0;

  font-size: 8px;
  font-weight: 800;

  letter-spacing: 0.045em;
  text-transform: uppercase;
}

.detail-row p {
  margin: 0;

  color: #59697e;

  font-size: 10.5px;
  line-height: 1.45;

  overflow-wrap: anywhere;
  white-space: pre-wrap;
}

.detail-row--justification p {
  color: #4d6077;
}

/* Footer */

.event-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;

  margin-top: 10px;
  padding-top: 8px;

  border-top: 1px solid #eef1f5;
}

.event-actor {
  display: inline-flex;
  min-width: 0;
  align-items: center;
  gap: 7px;

  color: #748298;

  font-size: 9.5px;
  font-weight: 550;
}

.actor-icon {
  display: grid;
  width: 22px;
  height: 22px;
  flex: 0 0 22px;
  place-items: center;

  border-radius: 50%;

  background: #edf2f8;
  color: #4e6888;
}

/* =========================================================
   STATES
   ========================================================= */

.history-state,
.history-error,
.history-empty {
  display: flex;
  min-height: 140px;
  align-items: center;
  justify-content: center;
  gap: 12px;

  margin: 18px 24px;
  padding: 22px;

  border: 1px solid #e3e8ef;
  border-radius: 12px;

  background: #fafbfd;

  color: #748197;
}

.history-error,
.history-empty {
  align-items: center;
}

.state-icon {
  display: grid;
  width: 40px;
  height: 40px;
  flex: 0 0 40px;
  place-items: center;

  border-radius: 10px;

  background: #eef2f7;
  color: #687c96;
}

.state-copy {
  display: grid;
  gap: 3px;
}

.state-copy strong {
  color: #354b66;

  font-size: 11.5px;
  font-weight: 750;
}

.state-copy p {
  margin: 0;

  color: #8a96a6;

  font-size: 10.5px;
  line-height: 1.45;
}

.retry-button {
  display: inline-flex;
  min-height: 31px;
  align-items: center;

  padding: 6px 10px;

  border: 1px solid #d7dee7;
  border-radius: 7px;

  background: #ffffff;
  color: #5e7086;

  font-family: inherit;
  font-size: 10px;
  font-weight: 700;

  cursor: pointer;
}

.retry-button:hover {
  border-color: #bdc9d7;
  background: #f6f8fb;
  color: #304f7e;
}

/* =========================================================
   RESPONSIVE
   ========================================================= */

@media (max-width: 760px) {
  .history-header {
    align-items: flex-start;
    flex-direction: column;

    padding: 17px 16px;
  }

  .timeline {
    padding: 16px;
  }

  .timeline-event {
    grid-template-columns: 30px minmax(0, 1fr);
    gap: 9px;
  }

  .timeline-node {
    width: 26px;
    height: 26px;
    flex-basis: 26px;
  }

  .event-header {
    flex-direction: column;
    gap: 6px;
  }

  .event-time {
    white-space: normal;
  }

  .history-state,
  .history-error,
  .history-empty {
    margin: 16px;
  }
}
</style>
