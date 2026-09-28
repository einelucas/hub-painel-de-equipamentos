<script setup lang="ts">
import { ArrowLeft } from "lucide-vue-next";
import type { Equipment, EquipmentDetail } from "~/types/equipment";

definePageMeta({ middleware: "auth" });
const route = useRoute();
const api = useApi();
const auth = useAuthStore();
const detail = ref<EquipmentDetail | null>(null);
const loading = ref(true);
const error = ref("");
const showEdit = ref(false);

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

async function loadEquipment(): Promise<void> {
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
    <NuxtLink class="admin-back" to="/dashboard"
      ><ArrowLeft :size="15" /> Voltar ao painel</NuxtLink
    >
    <div v-if="loading" class="surface detail-state">
      <span class="spinner" /> Carregando detalhe...
    </div>
    <div
      v-else-if="error"
      class="surface empty-state detail-state"
      role="alert"
    >
      <h2>Equipamento indisponível</h2>
      <p>{{ error }}</p>
      <button class="btn" @click="load">Tentar novamente</button>
    </div>
    <div v-else-if="detail" class="stack">
      <EquipmentOverview
        :equipment="detail.equipment"
        :current-stage="currentStage"
        :current-stage-label="currentStageLabel"
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

      <div class="detail-tabs" role="tablist">
        <button
          :class="{ active: tab === 'process' }"
          role="tab"
          @click="tab = 'process'"
        >
          Processo
        </button>
        <button
          :class="{ active: tab === 'components' }"
          role="tab"
          @click="tab = 'components'"
        >
          Componentes ({{ detail.components.length }})
        </button>
        <button
          :class="{ active: tab === 'suppliers' }"
          role="tab"
          data-testid="tab-suppliers"
          @click="tab = 'suppliers'"
        >
          Fornecedor
        </button>
        <button
          :class="{ active: tab === 'comments' }"
          role="tab"
          data-testid="tab-comments"
          @click="tab = 'comments'"
        >
          Comentários
        </button>
        <button
          :class="{ active: tab === 'history' }"
          role="tab"
          @click="tab = 'history'"
        >
          Histórico
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
.admin-back {
  align-items: center;
  gap: 6px;
}
.detail-state {
  display: flex;
  min-height: 280px;
  align-items: center;
  justify-content: center;
  gap: 12px;
}
.detail-tabs {
  display: flex;
  gap: 4px;
  border-bottom: 1px solid #e4e9f0;
}
.detail-tabs button {
  border: 0;
  border-bottom: 2px solid transparent;
  padding: 9px 14px;
  background: transparent;
  color: #7a879a;
  font-size: 12px;
  font-weight: 750;
}
.detail-tabs button.active {
  border-bottom-color: #304f7e;
  color: #2b3e58;
}
</style>
