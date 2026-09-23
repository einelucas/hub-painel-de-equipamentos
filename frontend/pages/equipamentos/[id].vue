<script setup lang="ts">
import { ArrowLeft, ArrowRight, Ban, Pencil, PlayCircle, Plus, RotateCcw, ShieldAlert, Wrench } from "lucide-vue-next";
import type { Equipment, EquipmentComponent, EquipmentDetail, WorkflowExceptionType } from "~/types/equipment";
import { formatCurrency, formatDateOnly, formatDateTime } from "~/utils/format";
import { negotiationStatusLabel, negotiationStatusTone } from "~/utils/negotiationStatus";
import { workNeedStatusLabel, workNeedStatusTone } from "~/utils/workNeedStatus";
import { EQUIPMENT_STAGES, stageTone } from "~/utils/stages";
import {
  OPERATIONAL_STATUS_LABELS,
  WORKFLOW_EXCEPTION_LABELS,
  type ProcessResource,
  advanceLabel as buildAdvanceLabel,
} from "~/utils/workflow";

definePageMeta({ middleware: "auth" });
const route = useRoute();
const api = useApi();
const auth = useAuthStore();
const detail = ref<EquipmentDetail | null>(null);
const loading = ref(true);
const error = ref("");
const showEdit = ref(false);
const showComponent = ref(false);
const editingComponent = ref<EquipmentComponent | null>(null);
const expandedComponentId = ref<string | null>(null);

function toggleComponentDeadlines(componentId: string): void {
  expandedComponentId.value = expandedComponentId.value === componentId ? null : componentId;
}
const tab = ref<"process" | "components" | "suppliers" | "comments" | "history">("process");
const equipmentId = computed(() => String(route.params.id));
const workflow = useEquipmentWorkflow(equipmentId);

const canWriteProcess = computed(() => auth.can("process:write"));
const canOperate = computed(() => auth.can("workflow:transition"));
const canRequestReopen = computed(() => auth.can("workflow:reopen_request"));
const canApproveReopen = computed(() => auth.can("workflow:reopen_approve"));

const currentStage = computed(
  () => workflow.transitions.value?.currentStage ?? detail.value?.equipment.currentStage ?? 0,
);
const currentStageLabel = computed(
  () => workflow.transitions.value?.currentStageLabel ?? detail.value?.equipment.stageName ?? "",
);
const advanceLabel = computed(() => buildAdvanceLabel(workflow.advance.value));
const operationalStatus = computed(
  () => workflow.operationalStatus.value?.operationalStatus ?? detail.value?.equipment.operationalStatus ?? "ACTIVE",
);
const isActive = computed(() => operationalStatus.value === "ACTIVE");
const lastOperationalEvent = computed(() => workflow.operationalStatus.value?.events[0] ?? null);

async function loadEquipment(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    detail.value = await api.get<EquipmentDetail>(`/equipments/${equipmentId.value}`);
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "Não foi possível carregar o equipamento.";
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

async function componentSaved(_component: EquipmentComponent): Promise<void> {
  showComponent.value = false;
  editingComponent.value = null;
  await loadEquipment();
}

function editComponent(component: EquipmentComponent): void {
  editingComponent.value = component;
  showComponent.value = true;
}

function closeComponent(): void {
  showComponent.value = false;
  editingComponent.value = null;
}

async function saveProcess(resource: ProcessResource, payload: Record<string, unknown>): Promise<void> {
  await workflow.saveProcess(resource, payload);
}

async function advanceStage(): Promise<void> {
  const option = workflow.advance.value;
  if (!option || !option.canExecute) return;
  if (await workflow.requestTransition(option.targetStage)) await load();
}

// --- Etapa 7B: estado operacional ---
const showStandby = ref(false);
const showLiftStandby = ref(false);
const showCancel = ref(false);
const showSanitation = ref(false);
const showEndSanitation = ref(false);

async function confirmStandby(text: string): Promise<void> {
  if (await workflow.enterStandby(text)) showStandby.value = false;
}
async function confirmLiftStandby(text: string): Promise<void> {
  if ((await workflow.liftStandby(text)) !== null) showLiftStandby.value = false;
}
async function confirmCancel(text: string): Promise<void> {
  if (await workflow.cancelEquipment(text)) showCancel.value = false;
}
async function confirmSanitation(text: string): Promise<void> {
  if (await workflow.enterSanitation(text)) showSanitation.value = false;
}
async function confirmEndSanitation(text: string): Promise<void> {
  if ((await workflow.endSanitation(text)) !== null) showEndSanitation.value = false;
}

// --- Etapa 7B: exceções de workflow ---
const showException = ref(false);
const exceptionType = ref<WorkflowExceptionType>("FIXED_SUPPLIER");
const exceptionJustification = ref("");

function openException(): void {
  exceptionType.value = "FIXED_SUPPLIER";
  exceptionJustification.value = "";
  showException.value = true;
}
async function confirmException(): Promise<void> {
  if (!exceptionJustification.value.trim()) return;
  if (await workflow.createException(exceptionType.value, exceptionJustification.value.trim())) {
    showException.value = false;
  }
}
async function cancelException(): Promise<void> {
  const active = workflow.activeException.value;
  if (active) await workflow.cancelException(active.id);
}

// --- Etapa 7C: reabertura com aprovação ---
const showReopenRequest = ref(false);
const reopenTargetStage = ref<number | "">("");
const reopenJustification = ref("");
const reopenStageOptions = computed(() =>
  EQUIPMENT_STAGES.map((label, index) => ({ index, label })).filter((item) => item.index < currentStage.value),
);

function openReopenRequest(): void {
  reopenTargetStage.value = "";
  reopenJustification.value = "";
  showReopenRequest.value = true;
}
async function confirmReopenRequest(): Promise<void> {
  if (reopenTargetStage.value === "" || !reopenJustification.value.trim()) return;
  if (await workflow.requestReopen(Number(reopenTargetStage.value), reopenJustification.value.trim())) {
    showReopenRequest.value = false;
  }
}

const showReopenDecision = ref(false);
const reopenDecisionMode = ref<"approve" | "reject">("approve");
const reopenDecisionNote = ref("");

function openReopenDecision(mode: "approve" | "reject"): void {
  reopenDecisionMode.value = mode;
  reopenDecisionNote.value = "";
  showReopenDecision.value = true;
}
async function confirmReopenDecision(): Promise<void> {
  const request = workflow.pendingReopenRequest.value;
  if (!request) return;
  const action = reopenDecisionMode.value === "approve" ? workflow.approveReopen : workflow.rejectReopen;
  if (await action(request.id, reopenDecisionNote.value.trim())) {
    showReopenDecision.value = false;
    await load();
  }
}

onMounted(load);
</script>

<template>
  <ModuleWorkspace eyebrow="Planejamento · Equipamentos" :title="detail?.equipment.name ?? 'Detalhe do equipamento'" description="Processo de aquisição, dados mestres, componentes e histórico.">
    <NuxtLink class="admin-back" to="/dashboard"><ArrowLeft :size="15" /> Voltar ao painel</NuxtLink>
    <div v-if="loading" class="surface detail-state"><span class="spinner" /> Carregando detalhe...</div>
    <div v-else-if="error" class="surface empty-state detail-state" role="alert"><h2>Equipamento indisponível</h2><p>{{ error }}</p><button class="btn" @click="load">Tentar novamente</button></div>
    <div v-else-if="detail" class="stack">
      <section class="surface">
        <div class="surface-header"><div><h2>Resumo</h2><p>Identificação e posição atual no processo.</p></div><button v-if="auth.can('equipments:write')" class="btn" @click="showEdit = true"><Pencil :size="15" /> Editar</button></div>
        <div class="surface-body detail-grid">
          <div class="detail-field"><span>Unidade</span><strong>{{ detail.equipment.unit.code }} · {{ detail.equipment.unit.name }}</strong></div>
          <div class="detail-field"><span>Contexto</span><strong>{{ detail.equipment.projectContext.code }} · {{ detail.equipment.projectContext.name }}</strong></div>
          <div class="detail-field"><span>Área</span><strong>{{ detail.equipment.area?.name ?? "—" }}</strong></div>
          <div class="detail-field"><span>Disciplina</span><strong>{{ detail.equipment.discipline?.name ?? "—" }}</strong></div>
          <div class="detail-field">
            <span>Pacotes de trabalho</span>
            <strong v-if="!detail.equipment.workPackages.length">—</strong>
            <div v-else class="wp-chips">
              <span v-for="item in detail.equipment.workPackages" :key="item.id" class="wp-chip">{{ item.code ?? item.name }}</span>
            </div>
          </div>
          <div class="detail-field"><span>Responsável</span><strong>{{ detail.equipment.responsibleUser?.name ?? "—" }}</strong></div>
          <div class="detail-field"><span>Fornecedor</span><strong>{{ detail.equipment.supplier?.name ?? "—" }}</strong></div>
          <div class="detail-field"><span>Etapa atual</span><strong><span class="stage-badge" :class="stageTone(currentStage)" data-testid="current-stage">{{ currentStage }} · {{ currentStageLabel }}</span></strong></div>
          <div class="detail-field">
            <span>Estado operacional</span>
            <strong>
              <span class="operational-badge" :class="`operational-badge--${operationalStatus.toLowerCase()}`" data-testid="operational-status-badge">
                {{ OPERATIONAL_STATUS_LABELS[operationalStatus] }}
              </span>
            </strong>
          </div>
          <div class="detail-field"><span>Startup</span><strong>{{ formatDateOnly(detail.equipment.startupAt) }}</strong></div>
          <div class="detail-field"><span>Criticidade</span><strong>{{ detail.equipment.criticality ?? "—" }}</strong></div>
          <div class="detail-field"><span>CAPEX estimado</span><strong>{{ formatCurrency(detail.equipment.capexEstimated) }}</strong></div>
          <div class="detail-field"><span>Valor total do projeto</span><strong>{{ formatCurrency(detail.equipment.projectTotalValue) }}</strong></div>
          <div class="detail-field">
            <span>Entrega contratual</span>
            <strong>
              <template v-if="detail.equipment.contractualDeliveryStart || detail.equipment.contractualDeliveryEnd">
                {{ formatDateOnly(detail.equipment.contractualDeliveryStart) }} — {{ formatDateOnly(detail.equipment.contractualDeliveryEnd) }}
              </template>
              <template v-else>—</template>
            </strong>
          </div>
        </div>
        <EquipmentWorkflowStepper :current-stage="currentStage" :next-stage-blocked="Boolean(workflow.advance.value?.missingRequirements.length)" />
        <p v-if="!isActive && lastOperationalEvent" class="operational-note" data-testid="operational-note">
          <strong>{{ OPERATIONAL_STATUS_LABELS[operationalStatus] }}</strong> desde {{ formatDateTime(lastOperationalEvent.occurredAt) }}
          por {{ lastOperationalEvent.actor?.name ?? "usuário removido" }} — {{ lastOperationalEvent.justification }}
        </p>
      </section>

      <section v-if="canOperate" class="surface">
        <div class="surface-header"><div><h2>Ações do processo</h2><p>Standby, cancelamento, saneamento e exceções de fluxo — sempre com justificativa e auditadas.</p></div></div>
        <div class="surface-body operational-actions">
          <template v-if="isActive">
            <button class="btn" data-testid="standby-button" @click="showStandby = true"><PlayCircle :size="15" /> Colocar em Standby</button>
            <button class="btn" data-testid="sanitation-button" @click="showSanitation = true"><Wrench :size="15" /> Colocar em Saneamento</button>
            <button class="btn danger" data-testid="cancel-button" @click="showCancel = true"><Ban :size="15" /> Cancelar equipamento</button>
            <button v-if="!workflow.activeException.value" class="btn" data-testid="exception-button" @click="openException"><ShieldAlert :size="15" /> Abrir exceção de fluxo</button>
          </template>
          <button v-else-if="operationalStatus === 'STANDBY'" class="btn primary" data-testid="lift-standby-button" @click="showLiftStandby = true">Remover Standby</button>
          <button v-else-if="operationalStatus === 'IN_SANITATION'" class="btn primary" data-testid="end-sanitation-button" @click="showEndSanitation = true">Encerrar Saneamento</button>
          <p v-else-if="operationalStatus === 'CANCELLED'" class="operational-hint">Cancelamento é definitivo — não é possível retomar o fluxo normal a partir daqui.</p>
        </div>

        <div v-if="workflow.activeException.value" class="surface-body exception-panel" data-testid="active-exception">
          <div class="exception-info">
            <span class="exception-badge">{{ WORKFLOW_EXCEPTION_LABELS[workflow.activeException.value.type] }}</span>
            <p>Alvo: fase {{ workflow.activeException.value.intendedTargetStage }} · {{ EQUIPMENT_STAGES[workflow.activeException.value.intendedTargetStage] }} — {{ workflow.activeException.value.justification }}</p>
          </div>
          <button v-if="isActive" class="text-button danger" @click="cancelException">Cancelar exceção</button>
        </div>
      </section>

      <section class="surface">
        <div class="surface-header"><div><h2>Reabertura</h2><p>Solicitação de reabertura de fase, com aprovação por permissão superior.</p></div></div>
        <div class="surface-body">
          <template v-if="workflow.pendingReopenRequest.value">
            <p class="reopen-pending" data-testid="pending-reopen-request">
              Reabertura para <strong>{{ workflow.pendingReopenRequest.value.targetStage }} · {{ workflow.pendingReopenRequest.value.targetStageLabel }}</strong>
              solicitada por {{ workflow.pendingReopenRequest.value.requestedBy?.name ?? "usuário removido" }}
              em {{ formatDateTime(workflow.pendingReopenRequest.value.requestedAt) }} — aguardando aprovação.
              <br><em>{{ workflow.pendingReopenRequest.value.justification }}</em>
            </p>
            <div v-if="canApproveReopen" class="reopen-decision-actions">
              <button class="btn primary" data-testid="approve-reopen" @click="openReopenDecision('approve')">Aprovar</button>
              <button class="btn danger" data-testid="reject-reopen" @click="openReopenDecision('reject')">Rejeitar</button>
            </div>
          </template>
          <button v-else-if="canRequestReopen && currentStage >= 1 && isActive" class="btn" data-testid="request-reopen-button" @click="openReopenRequest">
            <RotateCcw :size="15" /> Solicitar reabertura
          </button>
          <p v-else-if="currentStage < 1" class="operational-hint">Não há fase anterior para reabrir.</p>
        </div>
      </section>

      <section class="surface">
        <div class="surface-header"><div><h2>Prazos e planejamento</h2><p>Derivado dos componentes (FUN-001) — só leitura; recalculado a cada mudança nos componentes.</p></div></div>
        <div class="surface-body detail-grid">
          <div class="detail-field"><span>Lead time máximo</span><strong>{{ detail.equipment.calculated.maxLeadTimeDays === null ? "—" : `${detail.equipment.calculated.maxLeadTimeDays} dias` }}</strong></div>
          <div class="detail-field"><span>Dias antes do startup (máx.)</span><strong>{{ detail.equipment.calculated.maxPreStartDays === null ? "—" : `${detail.equipment.calculated.maxPreStartDays} dias` }}</strong></div>
          <div class="detail-field"><span>Frete máximo</span><strong>{{ detail.equipment.calculated.maxFreightDays === null ? "—" : `${detail.equipment.calculated.maxFreightDays} dias` }}</strong></div>
          <div class="detail-field"><span>Limite entrega em obra</span><strong>{{ formatDateOnly(detail.equipment.calculated.deliveryDeadline) }}</strong></div>
          <div class="detail-field">
            <span>Status necessidade da obra</span>
            <strong>
              <span
                class="negotiation-badge"
                :class="workNeedStatusTone(detail.equipment.calculated.workNeedStatus)"
                data-testid="work-need-status-badge"
              >{{ workNeedStatusLabel(detail.equipment.calculated.workNeedStatus) }}</span>
            </strong>
          </div>
          <div class="detail-field"><span>Limite contrato/OC</span><strong>{{ formatDateOnly(detail.equipment.calculated.contractOrderDeadline) }}</strong></div>
          <div class="detail-field">
            <span>Limite negociação</span>
            <strong>
              {{ formatDateOnly(detail.equipment.calculated.negotiationDeadline) }}
              <template v-if="detail.equipment.calculated.negotiationDaysRemaining !== null">
                ({{ detail.equipment.calculated.negotiationDaysRemaining >= 0 ? `${detail.equipment.calculated.negotiationDaysRemaining} dias restantes` : `${Math.abs(detail.equipment.calculated.negotiationDaysRemaining)} dias em atraso` }})
              </template>
            </strong>
          </div>
          <div class="detail-field">
            <span>Status negociação</span>
            <strong>
              <span
                class="negotiation-badge"
                :class="negotiationStatusTone(detail.equipment.calculated.negotiationStatus)"
                data-testid="negotiation-status-badge"
              >{{ negotiationStatusLabel(detail.equipment.calculated.negotiationStatus) }}</span>
            </strong>
          </div>
        </div>
      </section>

      <div class="detail-tabs" role="tablist">
        <button :class="{ active: tab === 'process' }" role="tab" @click="tab = 'process'">Processo</button>
        <button :class="{ active: tab === 'components' }" role="tab" @click="tab = 'components'">Componentes ({{ detail.components.length }})</button>
        <button :class="{ active: tab === 'suppliers' }" role="tab" data-testid="tab-suppliers" @click="tab = 'suppliers'">Fornecedor</button>
        <button :class="{ active: tab === 'comments' }" role="tab" data-testid="tab-comments" @click="tab = 'comments'">Comentários</button>
        <button :class="{ active: tab === 'history' }" role="tab" @click="tab = 'history'">Histórico</button>
      </div>

      <template v-if="tab === 'process'">
        <div v-if="workflow.loading.value" class="surface detail-state"><span class="spinner" /> Carregando processo...</div>
        <div v-else-if="workflow.error.value" class="surface empty-state detail-state" role="alert"><h2>Processo indisponível</h2><p>{{ workflow.error.value }}</p><button class="btn" @click="workflow.load()">Tentar novamente</button></div>
        <template v-else-if="workflow.processes.value">
          <div class="process-layout">
            <section class="surface">
              <div class="surface-header"><div><h2>Etapa atual · {{ currentStageLabel }}</h2><p>Preencha os dados desta etapa. Salvar não avança o processo.</p></div></div>
              <div class="surface-body">
                <p v-if="workflow.actionError.value" class="notice error" role="alert" data-testid="action-error">{{ workflow.actionError.value }}</p>
                <p v-else-if="workflow.actionSuccess.value" class="notice" data-testid="action-success">{{ workflow.actionSuccess.value }}</p>
                <EquipmentStageForm :stage="currentStage" :processes="workflow.processes.value" :editable="canWriteProcess" :saving="workflow.saving.value" @save="saveProcess" />
              </div>
            </section>

            <section class="surface">
              <div class="surface-header"><div><h2>Avanço do processo</h2><p>Os requisitos são validados pelo backend.</p></div></div>
              <div class="surface-body advance-panel">
                <WorkflowRequirements v-if="workflow.advance.value" :option="workflow.advance.value" />
                <p v-else class="requirements-final">Processo concluído — não há próxima etapa.</p>
                <button v-if="workflow.advance.value" class="btn primary advance-button" :disabled="!workflow.advance.value.canExecute || workflow.advancing.value" data-testid="advance-button" @click="advanceStage">
                  {{ workflow.advancing.value ? "Processando..." : advanceLabel }}<ArrowRight :size="15" />
                </button>
              </div>
            </section>
          </div>

          <section class="surface">
            <div class="surface-header"><div><h2>Processo completo</h2><p>Dados de todas as etapas. Editar aqui não muda a etapa atual — isso é feito no painel "Avanço do processo".</p></div></div>
            <div class="surface-body">
              <ProcessSummary
                :processes="workflow.processes.value"
                :editable="canWriteProcess"
                :saving="workflow.saving.value"
                @save="saveProcess"
              />
            </div>
          </section>

          <EquipmentContractsList
            :equipment-id="equipmentId"
            :contracts="workflow.processes.value.contracts"
            :editable="canWriteProcess"
            @changed="workflow.load()"
          />
          <EquipmentPurchaseRequestsList
            :equipment-id="equipmentId"
            :items="workflow.processes.value.purchaseRequests"
            :editable="canWriteProcess"
            @changed="workflow.load()"
          />
          <EquipmentPurchaseOrdersList
            :equipment-id="equipmentId"
            :items="workflow.processes.value.purchaseOrders"
            :editable="canWriteProcess"
            @changed="workflow.load()"
          />
        </template>
      </template>

      <section v-else-if="tab === 'components'" class="surface">
        <div class="surface-header"><div><h2>Componentes</h2><p>{{ detail.components.length }} subitem(ns) cadastrado(s).</p></div><button v-if="auth.can('equipments:write')" class="btn primary" @click="showComponent = true"><Plus :size="15" /> Adicionar componente</button></div>
        <div v-if="detail.components.length === 0" class="empty-state table-empty"><h2>Nenhum componente cadastrado</h2><p>Os componentes deste equipamento aparecerão aqui.</p></div>
        <div v-else class="table-wrap">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Componente</TableHead>
                <TableHead>Tag</TableHead>
                <TableHead>Startup</TableHead>
                <TableHead>Setor</TableHead>
                <TableHead>Lead time</TableHead>
                <TableHead>Pré-start</TableHead>
                <TableHead>Entrega contratual</TableHead>
                <TableHead>Frete</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              <template v-for="component in detail.components" :key="component.id">
                <TableRow>
                  <TableCell class="font-semibold">{{ component.name }}</TableCell>
                  <TableCell>{{ component.tag ?? "—" }}</TableCell>
                  <TableCell>{{ formatDateOnly(component.startupAt) }}</TableCell>
                  <TableCell>{{ component.sector ?? "—" }}</TableCell>
                  <TableCell>{{ component.leadTimeDays === null ? "—" : `${component.leadTimeDays} dias` }}</TableCell>
                  <TableCell>{{ component.preStartDays === null ? "—" : `${component.preStartDays} dias` }}</TableCell>
                  <TableCell>{{ formatDateOnly(component.contractDeliveryAt) }}</TableCell>
                  <TableCell>{{ component.freightDays === null ? "—" : `${component.freightDays} dias` }}</TableCell>
                  <TableCell class="component-actions">
                    <button class="text-button" :data-testid="`toggle-deadlines-${component.id}`" @click="toggleComponentDeadlines(component.id)">
                      {{ expandedComponentId === component.id ? "Ocultar prazos" : "Prazos calculados" }}
                    </button>
                    <button v-if="auth.can('equipments:write')" class="text-button" @click="editComponent(component)">Editar</button>
                  </TableCell>
                </TableRow>
                <TableRow v-if="expandedComponentId === component.id" class="deadlines-row">
                  <TableCell colspan="9">
                    <div class="deadlines-grid" :data-testid="`deadlines-${component.id}`">
                      <div class="detail-field"><span>Limite entrega em obra</span><strong>{{ formatDateOnly(component.calculated.deliveryDeadline) }}</strong></div>
                      <div class="detail-field"><span>Disponível coleta</span><strong>{{ formatDateOnly(component.calculated.availableForCollection) }}</strong></div>
                      <div class="detail-field"><span>Limite contrato/OC</span><strong>{{ formatDateOnly(component.calculated.contractOrderDeadline) }}</strong></div>
                      <div class="detail-field"><span>Limite negociação</span><strong>{{ formatDateOnly(component.calculated.negotiationDeadline) }}</strong></div>
                    </div>
                  </TableCell>
                </TableRow>
              </template>
            </TableBody>
          </Table>
        </div>
      </section>

      <EquipmentSuppliers v-else-if="tab === 'suppliers'" :equipment-id="equipmentId" />

      <EquipmentComments v-else-if="tab === 'comments'" :equipment-id="equipmentId" />

      <section v-else class="surface">
        <div class="surface-header"><div><h2>Histórico</h2><p>Transições de etapa, estados especiais e alterações relevantes do processo.</p></div></div>
        <div v-if="workflow.history.value.length === 0" class="empty-state table-empty"><h2>Sem registros</h2><p>As ações realizadas neste equipamento aparecerão aqui.</p></div>
        <div v-else class="timeline" data-testid="history-timeline">
          <article v-for="entry in workflow.history.value" :key="entry.id" class="timeline-item">
            <span class="timeline-dot" :class="{ 'timeline-dot--change': entry.kind === 'change', 'timeline-dot--status': entry.kind === 'operational_status' }" />
            <div>
              <strong>{{ entry.title }}</strong>
              <p v-if="entry.reason">{{ entry.reason }}</p>
              <p v-if="entry.justification" class="timeline-justification">{{ entry.justification }}</p>
              <small>{{ formatDateTime(entry.occurredAt) }} · {{ entry.actor?.name ?? "Usuário removido" }}</small>
            </div>
          </article>
        </div>
      </section>
    </div>

    <AppModal :open="showEdit" title="Editar equipamento" @close="showEdit = false"><EquipmentForm v-if="showEdit && detail" :unit-id="detail.equipment.unit.id" :equipment="detail.equipment" @saved="equipmentSaved" @cancel="showEdit = false" /></AppModal>
    <AppModal :open="showComponent" :title="editingComponent ? 'Editar componente' : 'Novo componente'" @close="closeComponent"><ComponentForm v-if="showComponent" :equipment-id="equipmentId" :component="editingComponent" @saved="componentSaved" @cancel="closeComponent" /></AppModal>

    <JustificationModal
      :open="showStandby"
      title="Colocar em Standby"
      message="O processo fica pausado na fase atual até o Standby ser removido."
      required
      :busy="workflow.busy.value"
      :error="workflow.actionError.value"
      confirm-label="Confirmar Standby"
      @confirm="confirmStandby"
      @close="showStandby = false"
    />
    <JustificationModal
      :open="showLiftStandby"
      title="Remover Standby"
      message="O equipamento volta a ficar ativo, na mesma fase em que estava."
      :busy="workflow.busy.value"
      :error="workflow.actionError.value"
      confirm-label="Remover Standby"
      @confirm="confirmLiftStandby"
      @close="showLiftStandby = false"
    />
    <JustificationModal
      :open="showCancel"
      title="Cancelar equipamento"
      message="Ação definitiva: o cancelamento fica registrado na fase atual e não é possível retomar o fluxo normal depois."
      required
      :busy="workflow.busy.value"
      :error="workflow.actionError.value"
      confirm-label="Confirmar cancelamento"
      @confirm="confirmCancel"
      @close="showCancel = false"
    />
    <JustificationModal
      :open="showSanitation"
      title="Colocar em Saneamento"
      message="O equipamento volta para a fase 0 · Nova Demanda e fica marcado como Em Saneamento até ser encerrado."
      required
      :busy="workflow.busy.value"
      :error="workflow.actionError.value"
      confirm-label="Confirmar Saneamento"
      @confirm="confirmSanitation"
      @close="showSanitation = false"
    />
    <JustificationModal
      :open="showEndSanitation"
      title="Encerrar Saneamento"
      message="O equipamento volta a ficar ativo, permanecendo na fase 0 · Nova Demanda — o usuário retoma o fluxo normal a partir daí."
      :busy="workflow.busy.value"
      :error="workflow.actionError.value"
      confirm-label="Encerrar Saneamento"
      @confirm="confirmEndSanitation"
      @close="showEndSanitation = false"
    />

    <AppModal :open="showException" title="Abrir exceção de fluxo" @close="showException = false">
      <form class="exception-form" @submit.prevent="confirmException">
        <label class="field">
          <span>Tipo *</span>
          <select v-model="exceptionType">
            <option value="FIXED_SUPPLIER">Fornecedor fixo (até a fase 5)</option>
            <option value="IMPORTATION">Importação (até a fase 7)</option>
          </select>
        </label>
        <p class="exception-hint">
          O avanço continua manual, fase por fase — a exceção só dispensa as validações específicas do tipo escolhido, sem pular etapas automaticamente.
        </p>
        <label class="field">
          <span>Justificativa *</span>
          <textarea v-model="exceptionJustification" maxlength="1000" required rows="3" />
        </label>
        <p v-if="workflow.actionError.value" class="notice error" role="alert">{{ workflow.actionError.value }}</p>
        <div class="form-actions">
          <button type="button" class="btn" @click="showException = false">Cancelar</button>
          <button type="submit" class="btn primary" :disabled="!exceptionJustification.trim() || workflow.busy.value">Abrir exceção</button>
        </div>
      </form>
    </AppModal>

    <AppModal :open="showReopenRequest" title="Solicitar reabertura" @close="showReopenRequest = false">
      <form class="exception-form" @submit.prevent="confirmReopenRequest">
        <label class="field">
          <span>Fase de destino *</span>
          <select v-model="reopenTargetStage" required>
            <option value="">Selecione</option>
            <option v-for="item in reopenStageOptions" :key="item.index" :value="item.index">{{ item.index }} · {{ item.label }}</option>
          </select>
        </label>
        <p class="exception-hint">O equipamento permanece na fase atual até a solicitação ser aprovada por um usuário com permissão de aprovação.</p>
        <label class="field">
          <span>Justificativa *</span>
          <textarea v-model="reopenJustification" maxlength="1000" required rows="3" />
        </label>
        <p v-if="workflow.actionError.value" class="notice error" role="alert">{{ workflow.actionError.value }}</p>
        <div class="form-actions">
          <button type="button" class="btn" @click="showReopenRequest = false">Cancelar</button>
          <button type="submit" class="btn primary" :disabled="reopenTargetStage === '' || !reopenJustification.trim() || workflow.busy.value">Solicitar</button>
        </div>
      </form>
    </AppModal>

    <AppModal :open="showReopenDecision" :title="reopenDecisionMode === 'approve' ? 'Aprovar reabertura' : 'Rejeitar reabertura'" @close="showReopenDecision = false">
      <form class="exception-form" @submit.prevent="confirmReopenDecision">
        <label class="field"><span>Nota (opcional)</span><textarea v-model="reopenDecisionNote" maxlength="1000" rows="3" /></label>
        <p v-if="workflow.actionError.value" class="notice error" role="alert">{{ workflow.actionError.value }}</p>
        <div class="form-actions">
          <button type="button" class="btn" @click="showReopenDecision = false">Cancelar</button>
          <button type="submit" class="btn primary" :disabled="workflow.busy.value">
            {{ reopenDecisionMode === "approve" ? "Confirmar aprovação" : "Confirmar rejeição" }}
          </button>
        </div>
      </form>
    </AppModal>
  </ModuleWorkspace>
</template>

<style scoped>
.admin-back { align-items: center; gap: 6px; }
.detail-state { display: flex; min-height: 280px; align-items: center; justify-content: center; gap: 12px; }
.detail-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 22px 18px; }
.detail-field { display: grid; align-content: start; gap: 5px; }
.detail-field > span { color: #7a879a; font-size: 10px; font-weight: 800; letter-spacing: .05em; text-transform: uppercase; }
.detail-field strong { color: #2b3e58; font-size: 13px; font-weight: 700; }
.detail-tabs { display: flex; gap: 4px; border-bottom: 1px solid #e4e9f0; }
.detail-tabs button { border: 0; border-bottom: 2px solid transparent; padding: 9px 14px; background: transparent; color: #7a879a; font-size: 12px; font-weight: 750; }
.detail-tabs button.active { border-bottom-color: #304f7e; color: #2b3e58; }
.process-layout { display: grid; grid-template-columns: minmax(0, 1.6fr) minmax(0, 1fr); gap: 18px; align-items: start; }
.advance-panel { display: grid; gap: 14px; }
.advance-button { justify-content: center; gap: 7px; }
.requirements-final { margin: 0; color: #477a32; font-size: 12px; font-weight: 700; }
.form-actions { display: flex; justify-content: flex-end; gap: 9px; }
.table-wrap { padding: 0 18px 18px; }
.table-empty { margin: auto; }
.stage-badge { display: inline-flex; border-radius: 999px; padding: 4px 8px; font-size: 11px; }
.stage-badge--new { background: #eef2f7; color: #53647a; }
.stage-badge--progress { background: #fff3df; color: #9b6418; }
.stage-badge--advanced { background: #e8f1fc; color: #2f5f9c; }
.stage-badge--complete { background: #eaf4e5; color: #477a32; }
.negotiation-badge { display: inline-flex; border-radius: 999px; padding: 4px 10px; font-size: 11px; font-weight: 750; }
.negotiation-badge--neutral { background: #eef2f7; color: #53647a; }
.negotiation-badge--complete { background: #eaf4e5; color: #477a32; }
.negotiation-badge--ok { background: #e8f1fc; color: #2f5f9c; }
.negotiation-badge--warning { background: #fff3df; color: #9b6418; }
.negotiation-badge--danger { background: #fbe8e8; color: #a53f3f; }
.operational-badge { display: inline-flex; border-radius: 999px; padding: 4px 10px; font-size: 11px; font-weight: 750; }
.operational-badge--active { background: #eaf4e5; color: #477a32; }
.operational-badge--standby { background: #fff3df; color: #9b6418; }
.operational-badge--cancelled { background: #fbe8e8; color: #a53f3f; }
.operational-badge--in_sanitation { background: #e8f1fc; color: #2f5f9c; }
.operational-note { margin: 0 20px 16px; padding: 9px 12px; border-radius: 8px; background: #fafbfc; border: 1px solid #edf1f5; color: #65748a; font-size: 12px; }
.operational-actions { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
.operational-hint { margin: 0; color: #8b96a5; font-size: 12px; }
.btn.danger { border-color: #e8c3bc; color: #a4453a; }
.exception-panel { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding-top: 0; border-top: 1px solid #edf1f5; }
.exception-info { display: grid; gap: 4px; }
.exception-badge { display: inline-flex; width: fit-content; border-radius: 999px; padding: 3px 9px; background: #eef2f7; color: #2b3e58; font-size: 11px; font-weight: 750; }
.exception-info p { margin: 0; color: #65748a; font-size: 12px; }
.exception-form { display: grid; gap: 14px; }
.exception-hint { margin: -6px 0 0; color: #8b96a5; font-size: 11.5px; }
.reopen-pending { margin: 0 0 12px; color: #65748a; font-size: 12px; }
.reopen-decision-actions { display: flex; gap: 9px; }
.wp-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.wp-chip { display: inline-flex; border-radius: 999px; padding: 3px 9px; font-size: 11px; font-weight: 700; background: #eef2f7; color: #2b3e58; }
.component-actions { display: flex; gap: 12px; white-space: nowrap; }
.deadlines-row { background: #fafbfc; }
.deadlines-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px 18px; padding: 6px 4px; }
@media (max-width: 900px) { .deadlines-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
.text-button { border: 0; padding: 4px; background: transparent; color: #304f7e; font-size: 12px; font-weight: 750; }
.text-button.danger { color: #a4453a; }
.timeline { display: grid; padding: 4px 20px 22px; }
.timeline-item { position: relative; display: grid; grid-template-columns: 20px 1fr; gap: 10px; padding: 14px 0; border-bottom: 1px solid #edf1f5; }
.timeline-item:last-child { border-bottom: 0; }
.timeline-dot { width: 10px; height: 10px; margin-top: 4px; border: 2px solid #304f7e; border-radius: 50%; background: #fff; }
.timeline-dot--change { border-color: #b8c3d1; }
.timeline-dot--status { border-color: #9b6418; background: #fff3df; }
.timeline-item strong { color: #2b3e58; font-size: 13px; }
.timeline-item p { margin: 4px 0; color: #65748a; font-size: 12px; }
.timeline-justification { font-style: italic; }
.timeline-item small { color: #8b96a5; font-size: 10px; }
@media (max-width: 1100px) { .process-layout { grid-template-columns: 1fr; } }
@media (max-width: 900px) { .detail-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 520px) { .detail-grid { grid-template-columns: 1fr; } }
</style>
