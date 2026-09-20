<script setup lang="ts">
import { Check, X } from "lucide-vue-next";
import type { TransitionOption } from "~/types/equipment";

defineProps<{ option: TransitionOption }>();
</script>

<template>
  <!-- A decisão de habilitar o avanço é do backend; aqui só é apresentada. -->
  <div class="requirements" data-testid="workflow-requirements">
    <p class="requirements-title">
      Próxima etapa: <strong>{{ option.targetStage }} · {{ option.targetStageLabel }}</strong>
    </p>
    <p v-if="option.requirements.length === 0" class="requirements-empty">
      Esta etapa não exige campos adicionais — o avanço é uma ação explícita.
    </p>
    <ul v-else class="requirements-list">
      <li
        v-for="requirement in option.requirements"
        :key="requirement.code"
        class="requirement"
        :class="{ 'requirement--done': requirement.satisfied }"
        :data-testid="`requirement-${requirement.code}`"
      >
        <Check v-if="requirement.satisfied" :size="13" />
        <X v-else :size="13" />
        <span>{{ requirement.message }}</span>
      </li>
    </ul>
    <p v-if="option.blockedReason" class="requirements-blocked">{{ option.blockedReason }}</p>
  </div>
</template>

<style scoped>
.requirements { display: grid; gap: 10px; }
.requirements-title { margin: 0; color: #53647a; font-size: 12px; }
.requirements-title strong { color: #2b3e58; }
.requirements-empty { margin: 0; color: #7a879a; font-size: 12px; }
.requirements-list { display: grid; margin: 0; padding: 0; gap: 7px; list-style: none; }
.requirement { display: grid; grid-template-columns: 16px 1fr; align-items: start; gap: 7px; color: #9b6418; font-size: 12px; }
.requirement--done { color: #477a32; }
.requirements-blocked { margin: 0; color: #a4453a; font-size: 12px; font-weight: 700; }
</style>
