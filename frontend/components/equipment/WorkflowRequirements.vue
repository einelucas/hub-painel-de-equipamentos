<script setup lang="ts">
import { Check, Undo2, X } from "lucide-vue-next";
import type { TransitionOption } from "~/types/equipment";

defineProps<{ option: TransitionOption }>();
</script>

<template>
  <!-- A decisão de habilitar o avanço é do backend; aqui só é apresentada. -->
  <div class="requirements" data-testid="workflow-requirements">
    <p class="requirements-title">
      Próxima etapa: <strong>{{ option.targetStage }} · {{ option.targetStageLabel }}</strong>
    </p>
    <p v-if="option.requirementGroups.length === 0" class="requirements-empty">
      Esta etapa não exige campos adicionais — o avanço é uma ação explícita.
    </p>
    <ul v-else class="requirements-list">
      <li
        v-for="group in option.requirementGroups"
        :key="group.code"
        class="requirement"
        :class="{ 'requirement--done': group.status !== 'MISSING' }"
        :data-testid="`requirement-${group.code}`"
      >
        <div class="requirement-row">
          <Check v-if="group.status === 'SATISFIED'" :size="13" />
          <Undo2 v-else-if="group.status === 'WAIVED'" :size="13" />
          <X v-else :size="13" />
          <span class="requirement-label">{{ group.message }}</span>
          <span v-if="group.status === 'WAIVED'" class="requirement-badge">Dispensado</span>
        </div>
      </li>
    </ul>
    <p v-if="option.blockedReason" class="requirements-blocked">{{ option.blockedReason }}</p>
    <p class="requirements-hint">
      Para marcar um requisito como "Não possui", use o botão junto da seção correspondente
      (Contratos, SC/OCI etc.) abaixo.
    </p>
  </div>
</template>

<style scoped>
.requirements { display: grid; gap: 10px; }
.requirements-title { margin: 0; color: #53647a; font-size: 12px; }
.requirements-title strong { color: #2b3e58; }
.requirements-empty { margin: 0; color: #7a879a; font-size: 12px; }
.requirements-list { display: grid; margin: 0; padding: 0; gap: 10px; list-style: none; }
.requirement { display: grid; gap: 6px; }
.requirement-row { display: grid; grid-template-columns: 16px 1fr auto; align-items: start; gap: 7px; color: #9b6418; font-size: 12px; }
.requirement--done .requirement-row { color: #477a32; }
.requirement-label { min-width: 0; }
.requirement-badge { display: inline-flex; border-radius: 999px; padding: 2px 8px; background: #e8f1fc; color: #2f5f9c; font-size: 10px; font-weight: 750; white-space: nowrap; }
.requirements-blocked { margin: 0; color: #a4453a; font-size: 12px; font-weight: 700; }
.requirements-hint { margin: 0; color: #8b96a5; font-size: 11px; }
</style>
