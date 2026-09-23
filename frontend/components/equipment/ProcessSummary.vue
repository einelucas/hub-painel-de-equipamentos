<script setup lang="ts">
import { computed, reactive } from "vue";
import type { EquipmentProcesses } from "~/types/equipment";
import { formatDateOnly } from "~/utils/format";
import { type ProcessResource, blankToNull } from "~/utils/workflow";

/**
 * Edição dos dados do processo é independente da etapa atual do equipamento
 * (GAP-008): o backend já não tem essa restrição, então cada bloco pode ser
 * editado a qualquer momento, inclusive com o equipamento concluído
 * (stage=8). Salvar um bloco nunca altera `current_stage` — quem faz isso é
 * o fluxo de transição (`EquipmentStageForm` + botão "Avançar"), que
 * continua sendo o único caminho para mudar de etapa.
 *
 * Etapa 7A: Contrato/SC-OCI/OC viraram listas 1:N — saíram daqui e têm
 * componentes próprios (`EquipmentContractsList` etc.), com o padrão
 * "lista compacta + Adicionar".
 */
const props = defineProps<{
  processes: EquipmentProcesses;
  editable: boolean;
  saving: boolean;
}>();
const emit = defineEmits<{
  save: [resource: ProcessResource, payload: Record<string, unknown>];
}>();

function bool(value: boolean): string {
  return value ? "Sim" : "Não";
}

function text(value: string | null): string {
  return value && value.trim() !== "" ? value : "—";
}

const editing = reactive<Record<ProcessResource, boolean>>({
  negotiation: false,
  legal: false,
});

const forms = reactive({
  negotiation: { equalized: false, negotiatedAt: "" },
  legal: { openedAt: "", ticketNumber: "", draftPrepared: false, draftApproved: false },
});

function startEdit(resource: ProcessResource): void {
  const { negotiation, legal } = props.processes;
  if (resource === "negotiation") {
    forms.negotiation.equalized = negotiation.equalized;
    forms.negotiation.negotiatedAt = negotiation.negotiatedAt ?? "";
  } else {
    forms.legal.openedAt = legal.openedAt ?? "";
    forms.legal.ticketNumber = legal.ticketNumber ?? "";
    forms.legal.draftPrepared = legal.draftPrepared;
    forms.legal.draftApproved = legal.draftApproved;
  }
  editing[resource] = true;
}

function cancelEdit(resource: ProcessResource): void {
  editing[resource] = false;
}

const PAYLOAD_BY_RESOURCE: Record<ProcessResource, () => Record<string, unknown>> = {
  negotiation: () => ({
    equalized: forms.negotiation.equalized,
    negotiatedAt: blankToNull(forms.negotiation.negotiatedAt),
  }),
  legal: () => ({
    openedAt: blankToNull(forms.legal.openedAt),
    ticketNumber: blankToNull(forms.legal.ticketNumber),
    draftPrepared: forms.legal.draftPrepared,
    draftApproved: forms.legal.draftApproved,
  }),
};

function save(resource: ProcessResource): void {
  emit("save", resource, PAYLOAD_BY_RESOURCE[resource]());
  editing[resource] = false;
}

const groups = computed(() => [
  {
    resource: "negotiation" as ProcessResource,
    title: "Negociação",
    fields: [
      { label: "Equalizada", value: bool(props.processes.negotiation.equalized) },
      { label: "Data da negociação", value: formatDateOnly(props.processes.negotiation.negotiatedAt) },
    ],
  },
  {
    resource: "legal" as ProcessResource,
    title: "Jurídico",
    fields: [
      { label: "Abertura", value: formatDateOnly(props.processes.legal.openedAt) },
      { label: "Chamado", value: text(props.processes.legal.ticketNumber) },
      { label: "Minuta elaborada", value: bool(props.processes.legal.draftPrepared) },
      { label: "Minuta aprovada", value: bool(props.processes.legal.draftApproved) },
    ],
  },
]);
</script>

<template>
  <div class="process-summary" data-testid="process-summary">
    <section v-for="group in groups" :key="group.title" class="process-group">
      <div class="process-group-header">
        <h3>{{ group.title }}</h3>
        <button
          v-if="editable && !editing[group.resource]"
          type="button"
          class="text-button"
          :data-testid="`edit-${group.resource}`"
          @click="startEdit(group.resource)"
        >
          Editar
        </button>
      </div>

      <div v-if="!editing[group.resource]" class="process-fields">
        <div v-for="field in group.fields" :key="field.label" class="detail-field">
          <span>{{ field.label }}</span><strong>{{ field.value }}</strong>
        </div>
      </div>

      <form v-else class="process-edit-form" :data-testid="`form-${group.resource}`" @submit.prevent="save(group.resource)">
        <div v-if="group.resource === 'negotiation'" class="edit-grid">
          <label class="field field-check">
            <input v-model="forms.negotiation.equalized" type="checkbox">
            <span>Negociação equalizada</span>
          </label>
          <label class="field"><span>Data da negociação</span><input v-model="forms.negotiation.negotiatedAt" type="date"></label>
        </div>

        <div v-else class="edit-grid">
          <label class="field"><span>Data de abertura</span><input v-model="forms.legal.openedAt" type="date"></label>
          <label class="field"><span>Número do chamado</span><input v-model="forms.legal.ticketNumber" maxlength="80"></label>
          <label class="field field-check"><input v-model="forms.legal.draftPrepared" type="checkbox"><span>Minuta elaborada</span></label>
          <label class="field field-check"><input v-model="forms.legal.draftApproved" type="checkbox"><span>Minuta aprovada</span></label>
        </div>

        <div class="edit-actions">
          <button type="button" class="btn" :disabled="saving" @click="cancelEdit(group.resource)">Cancelar</button>
          <button type="submit" class="btn primary" :disabled="saving" :data-testid="`save-${group.resource}`">
            {{ saving ? "Salvando..." : "Salvar" }}
          </button>
        </div>
      </form>
    </section>
  </div>
</template>

<style scoped>
.process-summary { display: grid; gap: 20px; }
.process-group-header { display: flex; align-items: center; justify-content: space-between; margin: 0 0 10px; }
.process-group h3 { margin: 0; color: #2b3e58; font-size: 12px; font-weight: 800; }
.text-button { color: #304f7e; font-size: 12px; font-weight: 750; text-decoration: none; background: none; border: none; cursor: pointer; padding: 0; }
.text-button:hover { text-decoration: underline; }
.process-fields { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 16px; }
.detail-field { display: grid; align-content: start; gap: 5px; }
.detail-field > span { color: #7a879a; font-size: 10px; font-weight: 800; letter-spacing: .05em; text-transform: uppercase; }
.detail-field strong { color: #2b3e58; font-size: 13px; font-weight: 700; }
.process-edit-form { display: grid; gap: 14px; padding: 12px; border: 1px solid #e2e7ee; border-radius: 8px; background: #fafbfc; }
.edit-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }
.field { display: grid; gap: 4px; font-size: 12px; }
.field span { color: #7a879a; font-size: 10px; font-weight: 800; letter-spacing: .05em; text-transform: uppercase; }
.field input, .field select { border: 1px solid #d8dee7; border-radius: 6px; padding: 7px 9px; font-size: 13px; }
.field-check { display: flex; flex-direction: row; align-items: center; gap: 8px; align-self: end; padding-bottom: 6px; }
.field-check input { width: 15px; height: 15px; }
.field-check span { color: #2b3e58; font-size: 12px; font-weight: 700; text-transform: none; letter-spacing: 0; }
.edit-actions { display: flex; justify-content: flex-end; gap: 9px; }
@media (max-width: 900px) { .process-fields, .edit-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 520px) { .process-fields, .edit-grid { grid-template-columns: 1fr; } }
</style>
