<script setup lang="ts">
import { computed, reactive, watch } from "vue";
import type { EquipmentProcesses } from "~/types/equipment";
import { type ProcessResource, blankToNull, resourceForStage } from "~/utils/workflow";

const props = defineProps<{
  stage: number;
  processes: EquipmentProcesses;
  editable: boolean;
  saving: boolean;
}>();
const emit = defineEmits<{
  save: [resource: ProcessResource, payload: Record<string, unknown>];
}>();

const resource = computed(() => resourceForStage(props.stage));

const form = reactive({
  equalized: false,
  negotiatedAt: "",
  openedAt: "",
  ticketNumber: "",
  draftPrepared: false,
  draftApproved: false,
});

function syncFromProcesses(): void {
  const { negotiation, legal } = props.processes;
  form.equalized = negotiation.equalized;
  form.negotiatedAt = negotiation.negotiatedAt ?? "";
  form.openedAt = legal.openedAt ?? "";
  form.ticketNumber = legal.ticketNumber ?? "";
  form.draftPrepared = legal.draftPrepared;
  form.draftApproved = legal.draftApproved;
}

watch(() => props.processes, syncFromProcesses, { immediate: true, deep: true });

const PAYLOAD_BY_RESOURCE: Record<ProcessResource, () => Record<string, unknown>> = {
  negotiation: () => ({ equalized: form.equalized, negotiatedAt: blankToNull(form.negotiatedAt) }),
  legal: () => ({
    openedAt: blankToNull(form.openedAt),
    ticketNumber: blankToNull(form.ticketNumber),
    draftPrepared: form.draftPrepared,
    draftApproved: form.draftApproved,
  }),
};

function submit(): void {
  if (!resource.value || !props.editable) return;
  emit("save", resource.value, PAYLOAD_BY_RESOURCE[resource.value]());
}
</script>

<template>
  <div v-if="stage === 0" class="stage-intro" data-testid="stage-form-intro">
    <p>
      O equipamento está na etapa inicial. Inicie a negociação para começar o processo de aquisição.
    </p>
  </div>
  <div v-else-if="stage === 8" class="stage-intro" data-testid="stage-form-done">
    <p>Processo concluído. Para corrigir algum dado de uma etapa já passada, use "Editar" no bloco correspondente em "Processo completo", abaixo.</p>
  </div>
  <div v-else-if="!resource" class="stage-intro" data-testid="stage-form-list">
    <p>Esta etapa é preenchida nas listas abaixo (Contratos, SC/OCI ou Ordens de Compra) — use "+ Adicionar" para criar um registro ou edite um já existente.</p>
  </div>
  <form v-else class="stage-form" data-testid="stage-form" @submit.prevent="submit">
    <fieldset :disabled="!editable">
      <div v-if="resource === 'negotiation'" class="form-grid">
        <label class="field field-check">
          <input v-model="form.equalized" type="checkbox">
          <span>Negociação equalizada</span>
        </label>
        <label class="field">
          <span>Data da negociação</span>
          <input v-model="form.negotiatedAt" type="date">
        </label>
      </div>

      <div v-else class="form-grid">
        <label class="field"><span>Data de abertura</span><input v-model="form.openedAt" type="date"></label>
        <label class="field"><span>Número do chamado</span><input v-model="form.ticketNumber" maxlength="80"></label>
        <label class="field field-check"><input v-model="form.draftPrepared" type="checkbox"><span>Minuta elaborada</span></label>
        <label class="field field-check"><input v-model="form.draftApproved" type="checkbox"><span>Minuta aprovada</span></label>
      </div>
    </fieldset>
    <div v-if="editable" class="form-actions">
      <button type="submit" class="btn" :disabled="saving" data-testid="save-process">
        {{ saving ? "Salvando..." : "Salvar alterações" }}
      </button>
    </div>
  </form>
</template>

<style scoped>
.stage-intro { padding: 4px 0 8px; color: #65748a; font-size: 13px; }
.stage-intro p { margin: 0; }
.stage-form { display: grid; gap: 16px; }
.stage-form fieldset { margin: 0; padding: 0; border: 0; }
.stage-form fieldset:disabled { opacity: .65; }
.form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
.field-check { display: flex; align-items: center; gap: 8px; align-self: end; padding-bottom: 8px; }
.field-check input { width: 15px; height: 15px; }
.field-check span { color: #2b3e58; font-size: 12px; font-weight: 700; }
.form-actions { display: flex; justify-content: flex-end; }
@media (max-width: 620px) { .form-grid { grid-template-columns: 1fr; } }
</style>
