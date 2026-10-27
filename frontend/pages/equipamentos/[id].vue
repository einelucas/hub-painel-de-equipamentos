<script setup lang="ts">
import {
  Boxes,
  Building2,
  History,
  MessageSquare,
  Workflow,
} from "lucide-vue-next";
import type { Equipment, EquipmentDetail } from "~/types/equipment";
import Button from "~/components/ui/Button.vue";
import { currentStageEnteredAt } from "~/utils/workflow";

definePageMeta({ middleware: "auth" });
const route = useRoute();
const api = useApi();
const auth = useAuthStore();
const detail = ref<EquipmentDetail | null>(null);
const loading = ref(true);
const error = ref("");
const showEdit = ref(false);
let loadStarted = false;

const tab = ref<
  "process" | "components" | "suppliers" | "comments" | "history"
>("process");
const equipmentId = computed(() => String(route.params.id));
const workflow = useEquipmentWorkflow(equipmentId);

const canWriteProcess = computed(() => auth.can("process:write"));
const canOperate = computed(() => auth.can("workflow:transition"));
const canRequestReopen = computed(() => auth.can("workflow:reopen_request"));
const canApproveReopen = computed(() => auth.can("workflow:reopen_approve"));

const currentStage = computed(
  () =>
    workflow.transitions.value?.currentStage ??
    detail.value?.equipment.currentStage ??
    0,
);
const currentStageLabel = computed(
  () =>
    workflow.transitions.value?.currentStageLabel ??
    detail.value?.equipment.stageName ??
    "",
);
const operationalStatus = computed(
  () =>
    workflow.operationalStatus.value?.operationalStatus ??
    detail.value?.equipment.operationalStatus ??
    "ACTIVE",
);
const isActive = computed(() => operationalStatus.value === "ACTIVE");
const lastOperationalEvent = computed(
  () => workflow.operationalStatus.value?.events[0] ?? null,
);
/** Quando a etapa atual começou — histórico do workflow + cadastro/Saneamento. */
const stageEnteredAt = computed(() =>
  currentStageEnteredAt({
    currentStage: currentStage.value,
    createdAt: detail.value?.equipment.createdAt ?? null,
    history: detail.value?.history ?? [],
    operationalEvents: workflow.operationalStatus.value?.events ?? [],
  }),
);

async function loadEquipment(): Promise<void> {
  if (loadStarted) return;
  loadStarted = true;
  loading.value = true;
  error.value = "";
  try {
    detail.value = await api.get<EquipmentDetail>(
      `/equipments/${equipmentId.value}`,
    );
  } catch (caught) {
    error.value =
      caught instanceof Error
        ? caught.message
        : "Não foi possível carregar o equipamento.";
  } finally {
    loading.value = false;
    loadStarted = false;
  }
}

async function load(): Promise<void> {
  await Promise.all([loadEquipment(), workflow.load()]);
}

async function equipmentSaved(_equipment: Equipment): Promise<void> {
  showEdit.value = false;
  await loadEquipment();
}

onMounted(load);
</script>

<template>
  <ModuleWorkspace
    eyebrow="Planejamento · Equipamentos"
    :title="detail?.equipment.name ?? 'Detalhe do equipamento'"
    description="Processo de aquisição, dados mestres, componentes e histórico."
  >
    <BackLink class="page-back" to="/dashboard">Voltar ao painel</BackLink>
    <div v-if="loading && !detail" class="surface detail-state" role="status">
      <span class="spinner" /> Carregando detalhe...
    </div>
    <div
      v-else-if="error"
      class="surface empty-state detail-state"
      role="alert"
    >
      <h2>Equipamento indisponível</h2>
      <p>{{ error }}</p>
      <Button variant="outline" @click="load">Tentar novamente</Button>
    </div>
    <div v-else-if="detail" class="stack" :aria-busy="loading">
      <div v-if="loading" class="progress-indeterminate" role="progressbar" aria-label="Atualizando" />
      <EquipmentOverview
        :equipment="detail.equipment"
        :current-stage="currentStage"
        :current-stage-label="currentStageLabel"
        :stage-entered-at="stageEnteredAt"
        :operational-status="operationalStatus"
        :last-operational-event="lastOperationalEvent"
        :next-stage-blocked="
          Boolean(
            workflow.advance.value?.requirementGroups.some(
              (group) => group.status === 'MISSING',
            ),
          )
        "
        :can-edit="auth.can('equipments:write')"
        @edit="showEdit = true"
      />

      <EquipmentOperationalActions
        :operational-status="operationalStatus"
        :can-operate="canOperate"
        :busy="workflow.busy.value"
        :action-error="workflow.actionError.value"
        :enter-standby="workflow.enterStandby"
        :lift-standby="workflow.liftStandby"
        :cancel-equipment="workflow.cancelEquipment"
        :enter-sanitation="workflow.enterSanitation"
        :end-sanitation="workflow.endSanitation"
      />

      <EquipmentReopenPanel
        :current-stage="currentStage"
        :is-active="isActive"
        :can-request-reopen="canRequestReopen"
        :can-approve-reopen="canApproveReopen"
        :pending-reopen-request="workflow.pendingReopenRequest.value"
        :busy="workflow.busy.value"
        :action-error="workflow.actionError.value"
        :request-reopen="workflow.requestReopen"
        :approve-reopen="workflow.approveReopen"
        :reject-reopen="workflow.rejectReopen"
        @decided="load"
      />

      <EquipmentDeadlines :calculated="detail.equipment.calculated" />

      <div
        class="detail-tabs"
        role="tablist"
        aria-label="Seções do equipamento"
      >
        <button
          type="button"
          :class="{ active: tab === 'process' }"
          role="tab"
          :aria-selected="tab === 'process'"
          @click="tab = 'process'"
        >
          <Workflow :size="16" aria-hidden="true" />
          <span>Processo</span>
        </button>
        <button
          type="button"
          :class="{ active: tab === 'components' }"
          role="tab"
          :aria-selected="tab === 'components'"
          @click="tab = 'components'"
        >
          <Boxes :size="16" aria-hidden="true" />
          <span>Componentes</span>
          <span class="detail-tab-count">{{ detail.components.length }}</span>
        </button>
        <button
          type="button"
          :class="{ active: tab === 'suppliers' }"
          role="tab"
          :aria-selected="tab === 'suppliers'"
          data-testid="tab-suppliers"
          @click="tab = 'suppliers'"
        >
          <Building2 :size="16" aria-hidden="true" />
          <span>Fornecedor</span>
        </button>
        <button
          type="button"
          :class="{ active: tab === 'comments' }"
          role="tab"
          :aria-selected="tab === 'comments'"
          data-testid="tab-comments"
          @click="tab = 'comments'"
        >
          <MessageSquare :size="16" aria-hidden="true" />
          <span>Comentários</span>
        </button>
        <button
          type="button"
          :class="{ active: tab === 'history' }"
          role="tab"
          :aria-selected="tab === 'history'"
          @click="tab = 'history'"
        >
          <History :size="16" aria-hidden="true" />
          <span>Histórico</span>
        </button>
      </div>

      <EquipmentProcessTab
        v-if="tab === 'process'"
        :equipment-id="equipmentId"
        :current-stage="currentStage"
        :current-stage-label="currentStageLabel"
        :can-write-process="canWriteProcess"
        :loading="workflow.loading.value"
        :error="workflow.error.value"
        :processes="workflow.processes.value"
        :advance="workflow.advance.value"
        :advancing="workflow.advancing.value"
        :saving="workflow.saving.value"
        :action-error="workflow.actionError.value"
        :action-success="workflow.actionSuccess.value"
        :save-process="workflow.saveProcess"
        :request-transition="workflow.requestTransition"
        :reload-process="workflow.load"
        :active-waiver-for="workflow.activeWaiverFor"
        @advanced="load"
      />

      <EquipmentComponentsTab
        v-else-if="tab === 'components'"
        :equipment-id="equipmentId"
        :components="detail.components"
        :can-edit="auth.can('equipments:write')"
        @saved="loadEquipment"
      />

      <EquipmentSuppliers
        v-else-if="tab === 'suppliers'"
        :equipment-id="equipmentId"
      />

      <EquipmentComments
        v-else-if="tab === 'comments'"
        :equipment-id="equipmentId"
      />

      <EquipmentHistory v-else :equipment-id="equipmentId" />
    </div>

    <AppModal
      :open="showEdit"
      title="Editar equipamento"
      @close="showEdit = false"
      ><EquipmentForm
        v-if="showEdit && detail"
        :unit-id="detail.equipment.unit.id"
        :equipment="detail.equipment"
        @saved="equipmentSaved"
        @cancel="showEdit = false"
    /></AppModal>
  </ModuleWorkspace>
</template>

<style scoped>
.detail-state {
  display: flex;
  min-height: 280px;
  align-items: center;
  justify-content: center;
  gap: 12px;
}
.detail-tabs {
  display: flex;
  align-items: center;
  gap: 4px;
  overflow-x: auto;
  border: 1px solid #d9e3ef;
  border-radius: 12px;
  background: #fff;
  padding: 4px;
  box-shadow: 0 6px 18px rgb(39 69 120 / 7%);
  scrollbar-width: none;
}
.detail-tabs::-webkit-scrollbar {
  display: none;
}
.detail-tabs button {
  display: inline-flex;
  flex: 0 0 auto;
  min-height: 36px;
  align-items: center;
  gap: 7px;
  border: 1px solid transparent;
  border-radius: 8px;
  padding: 8px 12px;
  background: transparent;
  color: #64748b;
  font-size: 12.5px;
  font-weight: 700;
  line-height: 1;
  white-space: nowrap;
  cursor: pointer;
  transition: background .15s, border-color .15s, color .15s, box-shadow .15s;
}
.detail-tabs button svg {
  flex: 0 0 auto;
  color: #8291a6;
}
.detail-tabs button:hover {
  background: #f3f7fc;
  color: #2b3e58;
}
.detail-tabs button:hover svg {
  color: #52657c;
}
.detail-tabs button:focus-visible {
  outline: 2px solid #304f7e;
  outline-offset: 2px;
}
.detail-tabs button.active {
  border-color: #cfe0f4;
  background: #e8f1fc;
  color: #27456f;
  box-shadow: inset 0 0 0 1px rgb(48 79 126 / 3%);
}
.detail-tabs button.active svg {
  color: #304f7e;
}
.detail-tab-count {
  display: inline-grid;
  min-width: 20px;
  height: 20px;
  place-items: center;
  border-radius: 999px;
  padding: 0 6px;
  background: #e6edf6;
  color: #52657c;
  font-size: 10.5px;
  font-weight: 800;
  line-height: 1;
}
.detail-tabs button.active .detail-tab-count {
  background: #fff;
  color: #27456f;
}
@media (prefers-reduced-motion: reduce) {
  .detail-tabs button {
    transition: none;
  }
}
</style>
