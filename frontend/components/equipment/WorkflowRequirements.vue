<script setup lang="ts">
import { Check, Undo2, X } from "lucide-vue-next";
import type { TransitionOption } from "~/types/equipment";

defineProps<{ option: TransitionOption }>();
</script>

<template>
  <!-- A decisão de habilitar o avanço é do backend; aqui só é apresentada. -->
  <div class="requirements" data-testid="workflow-requirements">
    <div class="requirements-next">
      <span class="requirements-eyebrow">Próxima etapa</span>
      <strong class="requirements-target">{{ option.targetStage }} · {{ option.targetStageLabel }}</strong>
    </div>

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
        <Check v-if="group.status === 'SATISFIED'" :size="15" />
        <Undo2 v-else-if="group.status === 'WAIVED'" :size="15" />
        <X v-else :size="15" />
        <span class="requirement-label">{{ group.message }}</span>
        <span v-if="group.status === 'WAIVED'" class="requirement-badge">Dispensado</span>
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
/* Escala de texto do app: rótulo 11px maiúsculo, corpo 13px, apoio 12px. */
.requirements { display: grid; gap: 12px; }
.requirements-next { display: grid; gap: 4px; }
.requirements-eyebrow { color: #56657a; font-size: 11px; font-weight: 800; letter-spacing: .03em; text-transform: uppercase; }
.requirements-target { color: #213758; font-size: 14px; font-weight: 800; line-height: 1.3; }
.requirements-empty { margin: 0; color: #7a879a; font-size: 13px; }
.requirements-list { display: grid; margin: 0; padding: 0; gap: 8px; list-style: none; }
/* Cada requisito é um bloco próprio, com a mesma borda/raio dos demais
   painéis e campos do app. */
.requirement { display: grid; grid-template-columns: 18px minmax(0, 1fr) auto; align-items: start; gap: 8px; border: 1px solid #e6ebf2; border-radius: 9px; padding: 9px 11px; background: #fff; color: #9b6418; font-size: 13px; line-height: 1.45; }
.requirement > svg { margin-top: 2px; }
.requirement--done { border-color: #dfe7f0; color: #477a32; }
.requirement-label { min-width: 0; }
.requirement-badge { display: inline-flex; min-height: 22px; align-items: center; border-radius: 999px; padding: 0 8px; background: #e8f1fc; color: #2f5f9c; font-size: 11px; font-weight: 750; white-space: nowrap; }
.requirements-blocked { margin: 0; color: #a4453a; font-size: 12.5px; font-weight: 700; }
.requirements-hint { margin: 0; color: #8b96a5; font-size: 12px; line-height: 1.5; }
</style>
