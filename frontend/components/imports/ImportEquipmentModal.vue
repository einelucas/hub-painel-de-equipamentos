<script setup lang="ts">
import { computed, provide, watch } from "vue";
import { Check } from "lucide-vue-next";
import { IMPORT_STEPS, useEquipmentImport, type ImportStep } from "~/composables/useEquipmentImport";
import { IMPORT_KEY } from "~/composables/useImportState";

/** Wizard "Importar equipamentos": estado local enquanto o modal está aberto (sem store global). */
const props = defineProps<{ open: boolean; unitId?: string }>();
const emit = defineEmits<{ close: [] }>();

const state = useEquipmentImport();
provide(IMPORT_KEY, state);
const { step, error, busy, statusMessage, locked, hasProgress, result, batches, totals, plan, selectedContext, files } = state;

watch(
  () => props.open,
  (isOpen) => {
    if (!isOpen) return;
    state.reset();
    void state.loadSetup(props.unitId ?? "");
  },
  { immediate: true },
);

/** Fechar no meio pede confirmação só quando já há análise feita. */
function close(): void {
  if (locked.value) return;
  if (hasProgress.value && !confirm("Fechar a importação? A análise já feita fica registrada, mas nada será importado.")) {
    return;
  }
  emit("close");
}

function stepIndex(key: string): number {
  return IMPORT_STEPS.findIndex((item) => item.key === key);
}

const currentIndex = computed(() => stepIndex(step.value));

function isDone(key: ImportStep, index: number): boolean {
  return index < currentIndex.value || (result.value !== null && key !== "result");
}

function plural(count: number, singular: string, pluralForm: string): string {
  return `${count} ${count === 1 ? singular : pluralForm}`;
}

/**
 * Cada estação da linha mostra o que aquela etapa já produziu; antes disso,
 * o que ela pede. É o resumo da importação sempre à vista.
 */
const stationNotes = computed<Record<ImportStep, string>>(() => {
  const groups = plan.value?.groups ?? [];
  const create = groups.reduce((sum, group) => sum + group.create, 0);
  const blocked = groups.reduce((sum, group) => sum + group.blocked, 0);
  const context = selectedContext.value;
  return {
    source: context
      ? `${context.code ?? context.name}${files.value.length ? ` · ${plural(files.value.length, "arquivo", "arquivos")}` : ""}`
      : "Destino e planilhas",
    analysis: batches.value.length
      ? `${plural(batches.value.length, "arquivo", "arquivos")} · ${totals.value.equipments} equip.`
      : "Leitura e validação",
    mapping: "Cadastros do Hub · opcional",
    plan: plan.value ? `${create} a criar · ${blocked} bloq.` : "Revisão antes de gravar",
    result: result.value
      ? result.value.hasDivergences
        ? "Com divergências"
        : `${result.value.created + result.value.updated} gravados`
      : "Gravação e conferência",
  };
});

const STEP_INTRO: Record<ImportStep, { title: string; text: string }> = {
  source: {
    title: "Escolha a obra e envie as planilhas",
    text: "Use os arquivos .xlsx exportados do board do Monday — um por fase com equipamentos.",
  },
  analysis: {
    title: "Confira o que foi lido",
    text: "Cada arquivo foi validado no servidor. Um erro em qualquer arquivo impede seguir.",
  },
  mapping: {
    title: "Associe valores aos cadastros do Hub",
    text: "Só altere quando o automático não for o desejado. Pendências não bloqueiam a importação.",
  },
  plan: {
    title: "Revise o plano antes de gravar",
    text: "Nada é gravado até você confirmar. Itens bloqueados impedem a confirmação.",
  },
  result: {
    title: "Importação gravada",
    text: "O Hub foi conferido contra as planilhas depois da gravação.",
  },
};
</script>

<template>
  <AppModal :open="props.open" title="Importar equipamentos" size="wide" @close="close">
    <div class="import-wizard" data-testid="import-wizard">
      <ol class="import-line" aria-label="Etapas da importação">
        <li
          v-for="(item, index) in IMPORT_STEPS"
          :key="item.key"
          class="station"
          :class="{ current: item.key === step, done: isDone(item.key, index) }"
          :aria-current="item.key === step ? 'step' : undefined"
          :data-testid="`import-stepper-${item.key}`"
        >
          <span class="station-marker" aria-hidden="true">
            <Check v-if="isDone(item.key, index)" :size="13" :stroke-width="3" />
            <template v-else>{{ index + 1 }}</template>
          </span>
          <span class="station-label">{{ item.label }}</span>
          <span class="station-note">{{ stationNotes[item.key] }}</span>
        </li>
      </ol>

      <header class="step-intro">
        <span class="step-kicker">Etapa {{ currentIndex + 1 }} de {{ IMPORT_STEPS.length }}</span>
        <h3>{{ STEP_INTRO[step].title }}</h3>
        <p>{{ STEP_INTRO[step].text }}</p>
      </header>

      <div v-if="busy && statusMessage" class="import-status" role="status" data-testid="import-status">
        <span><span class="spinner-small" aria-hidden="true" /> {{ statusMessage }}</span>
        <div class="progress-indeterminate" role="progressbar" aria-label="Processando" />
      </div>

      <p v-if="error" class="import-error" role="alert" data-testid="import-error">{{ error }}</p>

      <ImportSourceStep v-if="step === 'source'" />
      <ImportAnalysisStep v-else-if="step === 'analysis'" />
      <ImportMappingStep v-else-if="step === 'mapping'" />
      <ImportPlanStep v-else-if="step === 'plan'" />
      <ImportResultStep v-else-if="step === 'result'" @close="emit('close')" />
    </div>
  </AppModal>
</template>

<style scoped>
/* Tokens da importação: mesma família de cores do Hub, com mono para dados da planilha. */
.import-wizard {
  --ink: #1f3352;
  --steel: #304f7e;
  --wash: #f3f6fb;
  --rule: #dde5ef;
  --muted: #6b7a8f;
  --go: #3f7a2e;
  --go-wash: #eaf4e5;
  --caution: #8a5a12;
  --caution-wash: #fdf6e7;
  --stop: #a4453a;
  --stop-wash: #fbeeed;
  --mono: ui-monospace, "Cascadia Mono", "SFMono-Regular", Consolas, monospace;

  display: grid;
  gap: 18px;
}

/* ---------- Linha de processo (assinatura) ---------- */
.import-line {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  margin: -4px 0 0;
  padding: 16px 18px 14px;
  border: 1px solid var(--rule);
  border-radius: 14px;
  background: var(--wash);
  list-style: none;
}
.station {
  position: relative;
  display: grid;
  justify-items: start;
  gap: 3px;
  min-width: 0;
  padding-right: 10px;
}
/* trilho até a próxima estação; preenchido quando a etapa já passou */
.station:not(:last-child)::after {
  position: absolute;
  top: 12px;
  left: 30px;
  right: 4px;
  height: 2px;
  border-radius: 2px;
  background: var(--rule);
  content: "";
}
.station.done:not(:last-child)::after { background: var(--steel); }
.station-marker {
  position: relative;
  z-index: 1;
  display: inline-grid;
  width: 26px;
  height: 26px;
  place-items: center;
  border: 2px solid var(--rule);
  border-radius: 999px;
  background: #fff;
  color: var(--muted);
  font-family: var(--mono);
  font-size: 11.5px;
  font-weight: 700;
}
.station.done .station-marker { border-color: var(--steel); background: var(--steel); color: #fff; }
.station.current .station-marker {
  border-color: var(--steel);
  color: var(--steel);
  box-shadow: 0 0 0 4px rgb(48 79 126 / 14%);
}
.station-label { margin-top: 5px; color: var(--muted); font-size: 12px; font-weight: 800; }
.station.current .station-label, .station.done .station-label { color: var(--ink); }
.station-note {
  max-width: 100%;
  overflow: hidden;
  color: #8b96a5;
  font-family: var(--mono);
  font-size: 10.5px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.station.done .station-note { color: var(--steel); }

/* ---------- Abertura de cada etapa ---------- */
.step-intro { display: grid; gap: 3px; }
.step-kicker { color: var(--steel); font-family: var(--mono); font-size: 10.5px; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; }
.step-intro h3 { margin: 0; color: var(--ink); font-size: 17px; font-weight: 800; letter-spacing: -0.01em; }
.step-intro p { margin: 0; color: var(--muted); font-size: 12.5px; }

.import-status { display: grid; gap: 8px; border: 1px solid var(--rule); border-radius: 10px; background: var(--wash); padding: 10px 12px; color: var(--ink); font-size: 12.5px; font-weight: 700; }
.import-status .spinner-small { margin-right: 6px; vertical-align: -2px; }
.import-error { margin: 0; border-left: 3px solid var(--stop); border-radius: 8px; background: var(--stop-wash); padding: 9px 12px; color: var(--stop); font-size: 12px; font-weight: 700; }

/* ---------- Peças compartilhadas pelas etapas ---------- */
.import-wizard :deep(.import-step) { display: grid; gap: 14px; }
.import-wizard :deep(.import-hint) { margin: 0; color: var(--muted); font-size: 12px; line-height: 1.45; }
.import-wizard :deep(.import-panel) { display: grid; gap: 10px; border: 1px solid var(--rule); border-radius: 12px; background: #fff; padding: 14px 16px; }
.import-wizard :deep(.import-panel-head) { display: flex; flex-wrap: wrap; align-items: baseline; justify-content: space-between; gap: 4px 12px; }
.import-wizard :deep(.import-panel-head h4) { margin: 0; color: var(--ink); font-size: 13px; font-weight: 800; }
.import-wizard :deep(.import-count) { color: var(--muted); font-family: var(--mono); font-size: 11px; }
.import-wizard :deep(.mono) { font-family: var(--mono); }

/* Régua de números: contagens lidas da planilha ou do plano */
.import-wizard :deep(.import-ledger) {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  margin: 0;
  border: 1px solid var(--rule);
  border-radius: 12px;
  overflow: hidden;
}
.import-wizard :deep(.import-ledger > div) { display: grid; gap: 2px; padding: 11px 14px; border-right: 1px solid var(--rule); background: #fff; }
.import-wizard :deep(.import-ledger > div:last-child) { border-right: 0; }
.import-wizard :deep(.import-ledger dt) { color: var(--muted); font-size: 11px; font-weight: 700; }
.import-wizard :deep(.import-ledger dd) { margin: 0; color: var(--ink); font-family: var(--mono); font-size: 20px; font-weight: 700; font-variant-numeric: tabular-nums; }
.import-wizard :deep(.import-ledger .is-stop dd) { color: var(--stop); }
.import-wizard :deep(.import-ledger .is-caution dd) { color: var(--caution); }
.import-wizard :deep(.import-ledger .is-go dd) { color: var(--go); }

/* Tabelas de dados */
.import-wizard :deep(.import-table) { width: 100%; border: 1px solid var(--rule); border-radius: 12px; border-collapse: separate; border-spacing: 0; overflow: hidden; font-size: 12px; }
.import-wizard :deep(.import-table th) { background: var(--wash); color: var(--muted); font-size: 10.5px; font-weight: 800; letter-spacing: 0.04em; text-align: left; text-transform: uppercase; }
.import-wizard :deep(.import-table th), .import-wizard :deep(.import-table td) { border-bottom: 1px solid #edf1f6; padding: 8px 12px; color: var(--ink); }
.import-wizard :deep(.import-table tbody tr:last-child td) { border-bottom: 0; }
.import-wizard :deep(.import-table tfoot td) { border-top: 1px solid var(--rule); border-bottom: 0; background: var(--wash); font-weight: 800; }
.import-wizard :deep(.import-table .num) { font-family: var(--mono); font-variant-numeric: tabular-nums; text-align: right; }

/* Ações sempre visíveis no rodapé do modal, mesmo com conteúdo longo */
.import-wizard :deep(.import-actions) {
  position: sticky;
  bottom: -20px;
  z-index: 2;
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
  margin: 4px -20px -20px;
  padding: 14px 20px;
  border-top: 1px solid var(--rule);
  background: rgb(255 255 255 / 96%);
  backdrop-filter: blur(4px);
}

@media (max-width: 760px) {
  .import-line { grid-template-columns: 1fr; gap: 10px; }
  .station { grid-template-columns: auto minmax(0, 1fr); align-items: center; column-gap: 10px; }
  .station:not(:last-child)::after { display: none; }
  .station-label { margin-top: 0; }
  .station-note { grid-column: 2; }
}
@media (prefers-reduced-motion: no-preference) {
  .station-marker { transition: background-color 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease; }
  .station:not(:last-child)::after { transition: background-color 0.3s ease; }
}
</style>
