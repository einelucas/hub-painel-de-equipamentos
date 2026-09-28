<script setup lang="ts">
import { computed } from "vue";
import { Check, LockKeyhole } from "lucide-vue-next";
import { stepStates } from "~/utils/workflow";

const props = defineProps<{
  currentStage: number;
  nextStageBlocked?: boolean;
}>();

const steps = computed(() =>
  stepStates(props.currentStage, props.nextStageBlocked),
);

const currentPosition = computed(() => {
  const index = steps.value.findIndex((step) => step.state === "current");

  return index >= 0 ? index : 0;
});

const progress = computed(() => {
  if (steps.value.length <= 1) return 0;

  return (currentPosition.value / (steps.value.length - 1)) * 100;
});

const currentStep = computed(() =>
  steps.value.find((step) => step.state === "current"),
);
</script>

<template>
  <section
    class="workflow"
    data-testid="workflow-stepper"
    aria-label="Progresso do processo de aquisição"
  >
    <div class="workflow-header">
      <div>
        <span class="workflow-eyebrow"> Progresso da aquisição </span>

        <div class="workflow-current">
          <strong>
            {{ currentStep?.label ?? "Etapa atual" }}
          </strong>

          <span> Etapa {{ currentStage }} de {{ steps.length - 1 }} </span>
        </div>
      </div>

      <span class="workflow-percentage"> {{ Math.round(progress) }}% </span>
    </div>

    <div class="workflow-scroll">
      <div class="workflow-track">
        <div class="track-base" />

        <div class="track-progress" :style="{ width: `${progress}%` }" />

        <ol class="stepper">
          <li
            v-for="step in steps"
            :key="step.index"
            class="step"
            :class="`step--${step.state}`"
            :aria-current="step.state === 'current' ? 'step' : undefined"
            :data-state="step.state"
          >
            <div class="step-marker">
              <Check
                v-if="step.state === 'done'"
                :size="15"
                :stroke-width="2.5"
              />

              <LockKeyhole
                v-else-if="step.state === 'blocked'"
                :size="13"
                :stroke-width="2.2"
              />

              <span v-else>
                {{ step.index }}
              </span>
            </div>

            <div class="step-content">
              <span class="step-label">
                {{ step.label }}
              </span>

              <span v-if="step.state === 'current'" class="step-status">
                Etapa atual
              </span>

              <span
                v-else-if="step.state === 'blocked'"
                class="step-status step-status--blocked"
              >
                Bloqueada
              </span>
            </div>
          </li>
        </ol>
      </div>
    </div>
  </section>
</template>

<style scoped>
.workflow {
  --workflow-blue: #294e7c;
  --workflow-blue-light: #eaf2fb;

  --workflow-green: #4f7d3b;
  --workflow-green-light: #edf5e9;

  --workflow-gray: #dfe5ec;
  --workflow-text: #24364d;
  --workflow-muted: #7c8999;

  --workflow-amber: #a66b17;
  --workflow-amber-light: #fff4df;

  width: 100%;
  padding: 18px 22px 20px;
  border: 1px solid #e8ecf1;
  border-radius: 14px;
  background: #fff;
}

/* Header */

.workflow-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 24px;
}

.workflow-eyebrow {
  display: block;
  margin-bottom: 3px;

  color: var(--workflow-muted);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.workflow-current {
  display: flex;
  align-items: baseline;
  gap: 9px;
}

.workflow-current strong {
  color: var(--workflow-text);
  font-size: 14px;
  font-weight: 800;
}

.workflow-current span {
  color: var(--workflow-muted);
  font-size: 11px;
  font-weight: 600;
}

.workflow-percentage {
  display: grid;
  min-width: 46px;
  height: 27px;
  place-items: center;

  border-radius: 8px;
  background: var(--workflow-blue-light);

  color: var(--workflow-blue);
  font-size: 11px;
  font-weight: 800;
}

/* Estrutura */

.workflow-scroll {
  overflow-x: auto;
  padding: 2px 0 4px;
  scrollbar-width: thin;
}

.workflow-track {
  position: relative;
  min-width: 900px;
}

.track-base,
.track-progress {
  position: absolute;
  top: 16px;

  height: 3px;
  border-radius: 999px;
}

.track-base {
  right: calc(100% / 18);
  left: calc(100% / 18);
  background: var(--workflow-gray);
}

.track-progress {
  left: calc(100% / 18);

  max-width: calc(100% - (100% / 9));
  background: var(--workflow-blue);

  transition: width 300ms ease;
}

/* Steps */

.stepper {
  position: relative;
  z-index: 1;

  display: grid;
  grid-template-columns: repeat(9, minmax(95px, 1fr));

  margin: 0;
  padding: 0;

  list-style: none;
}

.step {
  display: flex;
  flex-direction: column;
  align-items: center;

  min-width: 95px;

  text-align: center;
}

.step-marker {
  display: grid;
  width: 32px;
  height: 32px;
  place-items: center;

  border: 2px solid var(--workflow-gray);
  border-radius: 50%;

  background: #fff;

  color: var(--workflow-muted);
  font-size: 11px;
  font-weight: 800;

  transition:
    transform 180ms ease,
    border-color 180ms ease,
    background 180ms ease,
    box-shadow 180ms ease;
}

.step-content {
  display: flex;
  flex-direction: column;
  align-items: center;

  margin-top: 8px;
}

.step-label {
  max-width: 125px;

  color: var(--workflow-muted);
  font-size: 10px;
  font-weight: 650;
  line-height: 1.25;
}

/* Concluído */

.step--done .step-marker {
  border-color: var(--workflow-green);
  background: var(--workflow-green-light);
  color: var(--workflow-green);
}

.step--done .step-label {
  color: #53647a;
}

/* Atual */

.step--current .step-marker {
  transform: scale(1.08);

  border-color: var(--workflow-blue);
  background: var(--workflow-blue);

  color: #fff;

  box-shadow:
    0 0 0 4px var(--workflow-blue-light),
    0 3px 9px rgb(41 78 124 / 18%);
}

.step--current .step-label {
  color: var(--workflow-text);
  font-weight: 800;
}

.step-status {
  margin-top: 3px;

  color: var(--workflow-blue);
  font-size: 8px;
  font-weight: 800;
  letter-spacing: 0.03em;
  text-transform: uppercase;
}

/* Bloqueado */

.step--blocked .step-marker {
  border-color: #e7c58d;
  background: var(--workflow-amber-light);
  color: var(--workflow-amber);
}

.step--blocked .step-label {
  color: var(--workflow-amber);
}

.step-status--blocked {
  color: var(--workflow-amber);
}

/* Mobile */

@media (max-width: 760px) {
  .workflow {
    padding: 16px 14px;
  }

  .workflow-header {
    margin-bottom: 20px;
  }

  .workflow-current {
    align-items: flex-start;
    flex-direction: column;
    gap: 2px;
  }

  .workflow-track {
    min-width: 780px;
  }

  .stepper {
    grid-template-columns: repeat(9, minmax(82px, 1fr));
  }

  .step-label {
    max-width: 100px;
    font-size: 9px;
  }
}
</style>
