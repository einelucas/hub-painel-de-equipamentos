<script setup lang="ts">
import { provide, watch } from "vue";
import { IMPORT_STEPS, useEquipmentImport } from "~/composables/useEquipmentImport";
import { IMPORT_KEY } from "~/composables/useImportState";

/** Wizard "Importar equipamentos": estado local enquanto o modal está aberto (sem store global). */
const props = defineProps<{ open: boolean; unitId?: string }>();
const emit = defineEmits<{ close: [] }>();

const state = useEquipmentImport();
provide(IMPORT_KEY, state);
const { step, error, hasProgress, result } = state;

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
  if (hasProgress.value && !confirm("Fechar a importação? A análise já feita fica registrada, mas nada será importado.")) {
    return;
  }
  emit("close");
}

function stepIndex(key: string): number {
  return IMPORT_STEPS.findIndex((item) => item.key === key);
}
</script>

<template>
  <AppModal :open="props.open" title="Importar equipamentos" @close="close">
    <div class="import-wizard" data-testid="import-wizard">
      <ol class="import-steps" aria-label="Etapas da importação">
        <li
          v-for="(item, index) in IMPORT_STEPS"
          :key="item.key"
          :class="{ current: item.key === step, done: index < stepIndex(step) || (result && item.key !== 'result') }"
          :aria-current="item.key === step ? 'step' : undefined"
          :data-testid="`import-stepper-${item.key}`"
        >
          <span class="dot">{{ index + 1 }}</span>{{ item.label }}
        </li>
      </ol>

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
.import-wizard { display: grid; gap: 14px; }
.import-steps { display: flex; flex-wrap: wrap; margin: 0; padding: 0 0 10px; gap: 6px 14px; border-bottom: 1px solid #e4e9f0; list-style: none; }
.import-steps li { display: inline-flex; align-items: center; gap: 6px; color: #8b96a5; font-size: 11.5px; font-weight: 750; }
.import-steps .dot { display: inline-grid; width: 20px; height: 20px; place-items: center; border-radius: 999px; background: #eef2f7; color: #6b7a8f; font-size: 10.5px; }
.import-steps li.current { color: #27456f; }
.import-steps li.current .dot { background: #304f7e; color: #fff; }
.import-steps li.done .dot { background: #eaf4e5; color: #477a32; }
.import-error { margin: 0; border-radius: 9px; background: #fbeeed; padding: 8px 11px; color: #a4453a; font-size: 12px; font-weight: 700; }
</style>
