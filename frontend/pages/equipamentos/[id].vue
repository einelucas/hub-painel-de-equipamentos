<script setup lang="ts">
import { mdiCubeOutline, mdiHistory, mdiMessageTextOutline, mdiOfficeBuildingOutline, mdiTimelineOutline } from "@mdi/js";
import type { Equipment, EquipmentDetail } from "~/types/equipment";
import { VBtn } from "vuetify/components";
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
      <VBtn variant="outlined" @click="load">Tentar novamente</VBtn>
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
        <VBtn
          type="button"
          :variant="tab === 'process' ? 'tonal' : 'text'"
          role="tab"
          :aria-selected="tab === 'process'"
          :prepend-icon="mdiTimelineOutline"
          @click="tab = 'process'"
        >
          <span>Processo</span>
        </VBtn>
        <VBtn
          type="button"
          :variant="tab === 'components' ? 'tonal' : 'text'"
          role="tab"
          :aria-selected="tab === 'components'"
          :prepend-icon="mdiCubeOutline"
          @click="tab = 'components'"
        >
          <span>Componentes</span>
          <span class="detail-tab-count">{{ detail.components.length }}</span>
        </VBtn>
        <VBtn
          type="button"
          :variant="tab === 'suppliers' ? 'tonal' : 'text'"
          role="tab"
          :aria-selected="tab === 'suppliers'"
          data-testid="tab-suppliers"
          :prepend-icon="mdiOfficeBuildingOutline"
          @click="tab = 'suppliers'"
        >
          <span>Fornecedor</span>
        </VBtn>
        <VBtn
          type="button"
          :variant="tab === 'comments' ? 'tonal' : 'text'"
          role="tab"
          :aria-selected="tab === 'comments'"
          data-testid="tab-comments"
          :prepend-icon="mdiMessageTextOutline"
          @click="tab = 'comments'"
        >
          <span>Comentários</span>
        </VBtn>
        <VBtn
          type="button"
          :variant="tab === 'history' ? 'tonal' : 'text'"
          role="tab"
          :aria-selected="tab === 'history'"
          :prepend-icon="mdiHistory"
          @click="tab = 'history'"
        >
          <span>Histórico</span>
        </VBtn>
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
</style>
