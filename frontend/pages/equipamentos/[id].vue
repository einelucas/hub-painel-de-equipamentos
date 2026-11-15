<script setup lang="ts">
import { Box, Building2, History, MessageSquareText, Workflow } from "lucide-vue-next";
import type { Equipment, EquipmentDetail } from "~/types/equipment";
import type { RealtimeChangeEvent } from "~/composables/useRealtimeSync";
import { VBtn, VProgress } from "vuetify/components";
import NavigationMenu from "~/components/ui/NavigationMenu.vue";
import { currentStageEnteredAt } from "~/utils/workflow";

definePageMeta({ middleware: "auth" });
const route = useRoute();
const api = useApi();
const auth = useAuthStore();
const detail = ref<EquipmentDetail | null>(null);
const loading = ref(true);
const error = ref("");
const showEdit = ref(false);
const formDirty = ref(false);
const externalChange = ref("");
const deletedExternally = ref(false);
const formKey = ref(0);
let equipmentRequestVersion = 0;
let unsubscribeSync: (() => void) | null = null;
const realtime = useRealtimeSync();

type EquipmentDetailTab = "process" | "components" | "suppliers" | "comments" | "history";
const tab = ref<EquipmentDetailTab>("process");
const detailNavigationItems = computed(() => [
  { value: "process", label: "Processo", icon: Workflow },
  {
    value: "components",
    label: "Componentes",
    icon: Box,
    badge: detail.value?.components.length ?? 0,
  },
  {
    value: "suppliers",
    label: "Fornecedor",
    icon: Building2,
    testId: "tab-suppliers",
  },
  {
    value: "comments",
    label: "Comentários",
    icon: MessageSquareText,
    testId: "tab-comments",
  },
  { value: "history", label: "Histórico", icon: History },
]);

function selectDetailTab(value: string): void {
  tab.value = value as EquipmentDetailTab;
}
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

async function loadEquipment(background = false): Promise<void> {
  const version = ++equipmentRequestVersion;
  if (!background) loading.value = true;
  if (version === equipmentRequestVersion) error.value = "";
  try {
    const result = await api.get<EquipmentDetail>(
      `/equipments/${equipmentId.value}`,
      undefined,
      { force: true },
    );
    if (version === equipmentRequestVersion) detail.value = result;
  } catch (caught) {
    if (version === equipmentRequestVersion) {
      error.value =
        caught instanceof Error
          ? caught.message
          : "Não foi possível carregar o equipamento.";
    }
  } finally {
    if (version === equipmentRequestVersion) loading.value = false;
  }
}

async function load(): Promise<void> {
  await Promise.all([loadEquipment(), workflow.load()]);
}

async function equipmentSaved(_equipment: Equipment): Promise<void> {
  showEdit.value = false;
  formDirty.value = false;
  externalChange.value = "";
  await loadEquipment();
}

async function realtimeChanged(event: RealtimeChangeEvent): Promise<void> {
  const equipmentDeleted =
    event.eventType === "deleted" &&
    (event.equipmentId === equipmentId.value ||
      (event.entityType === "project_context" &&
        event.projectContextId === detail.value?.equipment.projectContext.id));
  if (equipmentDeleted) {
    deletedExternally.value = true;
    externalChange.value = formDirty.value
      ? "Este registro foi excluído em outra sessão. Seu rascunho foi preservado, mas não poderá ser salvo."
      : "Este registro foi excluído em outra sessão.";
    return;
  }
  const relevant =
    event.eventType === "revalidate" ||
    (event.entityType === "equipment" && event.equipmentId === equipmentId.value);
  if (!relevant) return;
  if (showEdit.value && formDirty.value) {
    externalChange.value =
      "Existe uma versão mais recente deste equipamento. Seus campos não foram substituídos.";
    return;
  }
  await loadEquipment(true);
  if (showEdit.value) formKey.value += 1;
}

async function loadExternalVersion(): Promise<void> {
  showEdit.value = false;
  formDirty.value = false;
  externalChange.value = "";
  await loadEquipment(true);
  formKey.value += 1;
  showEdit.value = true;
}

function openEdit(): void {
  if (deletedExternally.value) return;
  formDirty.value = false;
  externalChange.value = "";
  showEdit.value = true;
}

function closeEdit(): void {
  showEdit.value = false;
  formDirty.value = false;
  if (!deletedExternally.value) externalChange.value = "";
}

onMounted(() => {
  unsubscribeSync = realtime.subscribe(realtimeChanged);
  void load();
});
onBeforeUnmount(() => unsubscribeSync?.());
</script>

<template>
  <ModuleWorkspace
    eyebrow="Planejamento · Equipamentos"
    :title="detail?.equipment.name ?? 'Detalhe do equipamento'"
    description="Processo de aquisição, dados mestres, componentes e histórico."
  >
    <BackLink class="page-back" to="/equipamentos">Voltar aos equipamentos</BackLink>
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
      <VAlert v-if="externalChange" :type="deletedExternally ? 'error' : 'warning'" variant="tonal">
        {{ externalChange }}
        <template v-if="showEdit && formDirty && !deletedExternally" #append>
          <VBtn size="small" variant="outlined" @click="loadExternalVersion">
            Carregar versão mais recente
          </VBtn>
        </template>
      </VAlert>
      <VProgress v-if="loading" color="primary" indeterminate aria-label="Atualizando" />
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
        @edit="openEdit"
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

      <NavigationMenu
        :model-value="tab"
        :items="detailNavigationItems"
        class="detail-navigation"
        aria-label="Seções do equipamento"
        @update:model-value="selectDetailTab"
      />

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
        :dismiss-action-success="workflow.dismissActionSuccess"
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
      size="wide"
      @close="closeEdit"
      ><EquipmentForm
        v-if="showEdit && detail"
        :key="formKey"
        :unit-id="detail.equipment.unit.id"
        :equipment="detail.equipment"
        @saved="equipmentSaved"
        @cancel="closeEdit"
        @dirty="formDirty = $event"
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
.detail-navigation {
  width: 100%;
  flex-wrap: nowrap;
  overflow-x: auto;
  box-shadow: 0 6px 18px rgb(39 69 120 / 7%);
  scrollbar-width: none;
}
.detail-navigation::-webkit-scrollbar {
  display: none;
}
.detail-navigation :deep(.analysis-nav__item) { flex-shrink: 0; }
</style>
