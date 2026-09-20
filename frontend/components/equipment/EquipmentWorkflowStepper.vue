<script setup lang="ts">
import { computed } from "vue";
import { Check } from "lucide-vue-next";
import { stepStates } from "~/utils/workflow";

const props = defineProps<{ currentStage: number; nextStageBlocked?: boolean }>();

const steps = computed(() => stepStates(props.currentStage, props.nextStageBlocked));
</script>

<template>
  <!-- Visual apenas: a etapa muda pelo fluxo validado no backend, nunca por clique aqui. -->
  <ol class="stepper" data-testid="workflow-stepper" aria-label="Progresso do processo de aquisição">
    <li
      v-for="step in steps"
      :key="step.index"
      class="step"
      :class="`step--${step.state}`"
      :aria-current="step.state === 'current' ? 'step' : undefined"
      :data-state="step.state"
    >
      <span class="step-marker">
        <Check v-if="step.state === 'done'" :size="13" />
        <template v-else>{{ step.index }}</template>
      </span>
      <span class="step-label">{{ step.label }}</span>
    </li>
  </ol>
</template>

<style scoped>
.stepper { display: flex; margin: 0; padding: 20px; list-style: none; gap: 4px; overflow-x: auto; }
.step { position: relative; display: grid; flex: 1 1 0; justify-items: center; min-width: 84px; gap: 7px; text-align: center; }
.step::before { position: absolute; top: 13px; right: 50%; left: -50%; height: 2px; background: #e4e9f0; content: ""; }
.step:first-child::before { display: none; }
.step--done::before, .step--current::before { background: #86a8d8; }
.step-marker { position: relative; z-index: 1; display: grid; width: 27px; height: 27px; place-items: center; border: 2px solid #e4e9f0; border-radius: 50%; background: #fff; color: #7a879a; font-size: 11px; font-weight: 800; }
.step-label { color: #7a879a; font-size: 10px; font-weight: 700; line-height: 1.3; }
.step--done .step-marker { border-color: #477a32; background: #eaf4e5; color: #477a32; }
.step--done .step-label { color: #53647a; }
.step--current .step-marker { border-color: #304f7e; background: #304f7e; color: #fff; box-shadow: 0 0 0 3px #e8f1fc; }
.step--current .step-label { color: #2b3e58; font-weight: 800; }
.step--blocked .step-marker { border-color: #e7c79a; background: #fff3df; color: #9b6418; }
@media (max-width: 760px) { .stepper { padding: 16px 12px; } .step { min-width: 74px; } .step-label { font-size: 9px; } }
</style>
