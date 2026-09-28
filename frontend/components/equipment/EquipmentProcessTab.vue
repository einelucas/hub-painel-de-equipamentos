<script setup lang="ts">
import { computed } from "vue";
import { ArrowRight } from "lucide-vue-next";
import type {
  EquipmentProcesses,
  RequirementGroup,
  RequirementWaiver,
  TransitionOption,
} from "~/types/equipment";
import {
  type ProcessResource,
  advanceLabel as buildAdvanceLabel,
} from "~/utils/workflow";

/**
 * Conteúdo da aba "Processo" — formulário da etapa atual, painel de avanço,
 * resumo do processo completo e as três listas 1:N (Contratos, SC/OCI,
 * Ordens de Compra). Só compõe os componentes já existentes; nenhuma regra
 * de transição/negócio é duplicada aqui. A instância de
 * `useEquipmentWorkflow` continua na página — chegam aqui só os dados já
 * carregados e as operações já prontas, via props tipadas.
 */
const props = defineProps<{
  equipmentId: string;
  currentStage: number;
  currentStageLabel: string;
  canWriteProcess: boolean;
  loading: boolean;
  error: string;
  processes: EquipmentProcesses | null;
  advance: TransitionOption | null;
  advancing: boolean;
  saving: boolean;
  actionError: string;
  actionSuccess: string;
  saveProcess: (
    resource: ProcessResource,
    payload: Record<string, unknown>,
  ) => Promise<boolean>;
  requestTransition: (targetStage: number) => Promise<boolean>;
  /** Recarrega só o workflow (processos/transições/dispensas) — usado pelos
   * `@changed` do formulário da etapa e das listas, e pelo "Tentar
   * novamente" deste painel. Diferente de `advanced`: avançar de etapa
   * muda `equipment.currentStage`, então a página recarrega tudo. */
  reloadProcess: () => Promise<void>;
  activeWaiverFor: (requirementGroupCode: string) => RequirementWaiver | null;
}>();
/** Emitido só após avançar de etapa com sucesso — a página recarrega o
 * equipamento inteiro (não só o workflow), igual ao `advanceStage` original. */
const emit = defineEmits<{ advanced: [] }>();

const advanceLabel = computed(() => buildAdvanceLabel(props.advance));

function requirementGroupByCode(code: string): RequirementGroup | null {
  return (
    props.advance?.requirementGroups.find((group) => group.code === code) ??
    null
  );
}
const stageRequirementGroup = computed(
  () => props.advance?.requirementGroups[0] ?? null,
);
const contractRequirementGroup = computed(() =>
  requirementGroupByCode("CONTRACT"),
);
const purchaseRequestRequirementGroup = computed(() =>
  requirementGroupByCode("PURCHASE_REQUEST"),
);

async function advanceStage(): Promise<void> {
  if (!props.advance || !props.advance.canExecute) return;
  if (await props.requestTransition(props.advance.targetStage))
    emit("advanced");
}
</script>

<template>
  <div v-if="loading" class="surface detail-state">
    <span class="spinner" /> Carregando processo...
  </div>
  <div v-else-if="error" class="surface empty-state detail-state" role="alert">
    <h2>Processo indisponível</h2>
    <p>{{ error }}</p>
    <button class="btn" @click="reloadProcess">Tentar novamente</button>
  </div>
  <template v-else-if="processes">
    <div class="process-layout">
      <section class="surface">
        <div class="surface-header">
          <div>
            <h2>Etapa atual · {{ currentStageLabel }}</h2>
            <p>Preencha os dados desta etapa. Salvar não avança o processo.</p>
          </div>
        </div>
        <div class="surface-body">
          <p
            v-if="actionError"
            class="notice error"
            role="alert"
            data-testid="action-error"
          >
            {{ actionError }}
          </p>
          <p
            v-else-if="actionSuccess"
            class="notice"
            data-testid="action-success"
          >
            {{ actionSuccess }}
          </p>
          <EquipmentStageForm
            :stage="currentStage"
            :processes="processes"
            :editable="canWriteProcess"
            :saving="saving"
            :equipment-id="equipmentId"
            :requirement-group="stageRequirementGroup"
            @save="saveProcess"
            @changed="reloadProcess"
          />
        </div>
      </section>

      <section class="surface">
        <div class="surface-header">
          <div>
            <h2>Avanço do processo</h2>
            <p>Os requisitos são validados pelo backend.</p>
          </div>
        </div>
        <div class="surface-body advance-panel">
          <WorkflowRequirements v-if="advance" :option="advance" />
          <p v-else class="requirements-final">
            Processo concluído — não há próxima etapa.
          </p>
          <button
            v-if="advance"
            class="btn primary advance-button"
            :disabled="!advance.canExecute || advancing"
            data-testid="advance-button"
            @click="advanceStage"
          >
            {{ advancing ? "Processando..." : advanceLabel
            }}<ArrowRight :size="15" />
          </button>
        </div>
      </section>
    </div>

    <section class="surface">
      <div class="surface-header">
        <div>
          <h2>Processo completo</h2>
          <p>
            Dados de todas as etapas. Editar aqui não muda a etapa atual — isso
            é feito no painel "Avanço do processo".
          </p>
        </div>
      </div>
      <div class="surface-body">
        <ProcessSummary
          :processes="processes"
          :editable="canWriteProcess"
          :saving="saving"
          @save="saveProcess"
        />
      </div>
    </section>

    <EquipmentContractsList
      :equipment-id="equipmentId"
      :contracts="processes.contracts"
      :editable="canWriteProcess"
      :requirement-group="contractRequirementGroup"
      :requirement-stage="currentStage"
      :requirement-waiver="activeWaiverFor('CONTRACT')"
      @changed="reloadProcess"
    />
    <EquipmentPurchaseRequestsList
      :equipment-id="equipmentId"
      :items="processes.purchaseRequests"
      :editable="canWriteProcess"
      :requirement-group="purchaseRequestRequirementGroup"
      :requirement-stage="currentStage"
      :requirement-waiver="activeWaiverFor('PURCHASE_REQUEST')"
      @changed="reloadProcess"
    />
    <EquipmentPurchaseOrdersList
      :equipment-id="equipmentId"
      :items="processes.purchaseOrders"
      :editable="canWriteProcess"
      @changed="reloadProcess"
    />
  </template>
</template>

<style scoped>
.detail-state {
  display: flex;
  min-height: 280px;
  align-items: center;
  justify-content: center;
  gap: 12px;
}
.process-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) minmax(0, 1fr);
  gap: 18px;
  align-items: start;
}
.advance-panel {
  display: grid;
  gap: 14px;
}
.advance-button {
  justify-content: center;
  gap: 7px;
}
.requirements-final {
  margin: 0;
  color: #477a32;
  font-size: 12px;
  font-weight: 700;
}
@media (max-width: 1100px) {
  .process-layout {
    grid-template-columns: 1fr;
  }
}
</style>
