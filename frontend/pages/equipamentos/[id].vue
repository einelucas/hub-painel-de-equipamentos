<script setup lang="ts">
import { ArrowLeft, ArrowRight, Pencil, Plus, RotateCcw } from "lucide-vue-next";
import type { Equipment, EquipmentComponent, EquipmentDetail } from "~/types/equipment";
import { formatCurrency, formatDate } from "~/utils/format";
import { stageTone } from "~/utils/stages";
import { type ProcessResource, advanceLabel as buildAdvanceLabel } from "~/utils/workflow";

definePageMeta({ middleware: "auth" });
const route = useRoute();
const api = useApi();
const auth = useAuthStore();
const detail = ref<EquipmentDetail | null>(null);
const loading = ref(true);
const error = ref("");
const showEdit = ref(false);
const showComponent = ref(false);
const showReopen = ref(false);
const reopenReason = ref("");
const editingComponent = ref<EquipmentComponent | null>(null);
const tab = ref<"process" | "components" | "suppliers" | "history">("process");
const equipmentId = computed(() => String(route.params.id));
const workflow = useEquipmentWorkflow(equipmentId);

const canWriteProcess = computed(() => auth.can("process:write"));
const currentStage = computed(
  () => workflow.transitions.value?.currentStage ?? detail.value?.equipment.currentStage ?? 0,
);
const currentStageLabel = computed(
  () => workflow.transitions.value?.currentStageLabel ?? detail.value?.equipment.stageName ?? "",
);
const advanceLabel = computed(() => buildAdvanceLabel(workflow.advance.value));

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

async function confirmReopen(): Promise<void> {
  const option = workflow.reopen.value;
  if (!option || !reopenReason.value.trim()) return;
  if (await workflow.requestTransition(option.targetStage, reopenReason.value)) {
    showReopen.value = false;
    reopenReason.value = "";
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
          <div class="detail-field"><span>Etapa atual</span><strong><span class="stage-badge" :class="stageTone(currentStage)" data-testid="current-stage">{{ currentStage }} · {{ currentStageLabel }}</span></strong></div>
          <div class="detail-field"><span>Startup</span><strong>{{ formatDate(detail.equipment.startupAt) }}</strong></div>
          <div class="detail-field"><span>Criticidade</span><strong>{{ detail.equipment.criticality ?? "—" }}</strong></div>
          <div class="detail-field"><span>CAPEX estimado</span><strong>{{ formatCurrency(detail.equipment.capexEstimated) }}</strong></div>
        </div>
        <EquipmentWorkflowStepper :current-stage="currentStage" :next-stage-blocked="Boolean(workflow.advance.value?.missingRequirements.length)" />
      </section>

      <div class="detail-tabs" role="tablist">
        <button :class="{ active: tab === 'process' }" role="tab" @click="tab = 'process'">Processo</button>
        <button :class="{ active: tab === 'components' }" role="tab" @click="tab = 'components'">Componentes ({{ detail.components.length }})</button>
        <button :class="{ active: tab === 'suppliers' }" role="tab" data-testid="tab-suppliers" @click="tab = 'suppliers'">Fornecedores</button>
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
                <button v-if="workflow.reopen.value?.canExecute" class="btn reopen-button" data-testid="reopen-button" @click="showReopen = true"><RotateCcw :size="15" /> Reabrir negociação</button>
                <p v-if="workflow.reopen.value" class="reopen-note">Reabertura é uma regra provisória, restrita ao perfil administrativo e sempre auditada.</p>
              </div>
            </section>
          </div>

          <section class="surface">
            <div class="surface-header"><div><h2>Processo completo</h2><p>Dados de todas as etapas, em modo leitura.</p></div></div>
            <div class="surface-body"><ProcessSummary :processes="workflow.processes.value" /></div>
          </section>
        </template>
      </template>

      <section v-else-if="tab === 'components'" class="surface">
        <div class="surface-header"><div><h2>Componentes</h2><p>{{ detail.components.length }} subitem(ns) cadastrado(s).</p></div><button v-if="auth.can('equipments:write')" class="btn primary" @click="showComponent = true"><Plus :size="15" /> Adicionar componente</button></div>
        <div v-if="detail.components.length === 0" class="empty-state table-empty"><h2>Nenhum componente cadastrado</h2><p>Os componentes deste equipamento aparecerão aqui.</p></div>
        <div v-else class="table-wrap"><Table><TableHeader><TableRow><TableHead>Componente</TableHead><TableHead>Tag</TableHead><TableHead>Setor</TableHead><TableHead>Lead time</TableHead><TableHead>Pré-start</TableHead><TableHead>Entrega contratual</TableHead><TableHead>Frete</TableHead><TableHead /></TableRow></TableHeader><TableBody><TableRow v-for="component in detail.components" :key="component.id"><TableCell class="font-semibold">{{ component.name }}</TableCell><TableCell>{{ component.tag ?? "—" }}</TableCell><TableCell>{{ component.sector ?? "—" }}</TableCell><TableCell>{{ component.leadTimeDays === null ? "—" : `${component.leadTimeDays} dias` }}</TableCell><TableCell>{{ component.preStartDays === null ? "—" : `${component.preStartDays} dias` }}</TableCell><TableCell>{{ formatDate(component.contractDeliveryAt) }}</TableCell><TableCell>{{ component.freightDays === null ? "—" : `${component.freightDays} dias` }}</TableCell><TableCell><button v-if="auth.can('equipments:write')" class="text-button" @click="editComponent(component)">Editar</button></TableCell></TableRow></TableBody></Table></div>
      </section>

      <EquipmentSuppliers v-else-if="tab === 'suppliers'" :equipment-id="equipmentId" />

      <section v-else class="surface">
        <div class="surface-header"><div><h2>Histórico</h2><p>Transições de etapa e alterações relevantes do processo.</p></div></div>
        <div v-if="workflow.history.value.length === 0" class="empty-state table-empty"><h2>Sem registros</h2><p>As ações realizadas neste equipamento aparecerão aqui.</p></div>
        <div v-else class="timeline" data-testid="history-timeline">
          <article v-for="entry in workflow.history.value" :key="entry.id" class="timeline-item">
            <span class="timeline-dot" :class="{ 'timeline-dot--change': entry.kind === 'change' }" />
            <div>
              <strong>{{ entry.title }}</strong>
              <p v-if="entry.reason">{{ entry.reason }}</p>
              <small>{{ formatDate(entry.occurredAt, true) }} · {{ entry.actor?.name ?? "Usuário removido" }}</small>
            </div>
          </article>
        </div>
      </section>
    </div>

    <AppModal :open="showEdit" title="Editar equipamento" @close="showEdit = false"><EquipmentForm v-if="showEdit && detail" :unit-id="detail.equipment.unit.id" :equipment="detail.equipment" @saved="equipmentSaved" @cancel="showEdit = false" /></AppModal>
    <AppModal :open="showComponent" :title="editingComponent ? 'Editar componente' : 'Novo componente'" @close="closeComponent"><ComponentForm v-if="showComponent" :equipment-id="equipmentId" :component="editingComponent" @saved="componentSaved" @cancel="closeComponent" /></AppModal>
    <AppModal :open="showReopen" title="Reabrir negociação" @close="showReopen = false">
      <form class="reopen-form" @submit.prevent="confirmReopen">
        <p class="reopen-warning">A etapa voltará para <strong>1 · Negociação</strong>. A ação fica registrada no histórico com o motivo informado.</p>
        <label class="field"><span>Motivo *</span><textarea v-model="reopenReason" maxlength="500" required rows="3" /></label>
        <p v-if="workflow.actionError.value" class="notice error" role="alert">{{ workflow.actionError.value }}</p>
        <div class="form-actions">
          <button type="button" class="btn" @click="showReopen = false">Cancelar</button>
          <button type="submit" class="btn primary" :disabled="!reopenReason.trim() || workflow.advancing.value">Confirmar reabertura</button>
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
.reopen-button { justify-content: center; gap: 7px; }
.reopen-note { margin: 0; color: #8b96a5; font-size: 11px; }
.requirements-final { margin: 0; color: #477a32; font-size: 12px; font-weight: 700; }
.reopen-form { display: grid; gap: 14px; }
.reopen-warning { margin: 0; color: #65748a; font-size: 12px; }
.form-actions { display: flex; justify-content: flex-end; gap: 9px; }
.table-wrap { padding: 0 18px 18px; }
.table-empty { margin: auto; }
.stage-badge { display: inline-flex; border-radius: 999px; padding: 4px 8px; font-size: 11px; }
.stage-badge--new { background: #eef2f7; color: #53647a; }
.stage-badge--progress { background: #fff3df; color: #9b6418; }
.stage-badge--advanced { background: #e8f1fc; color: #2f5f9c; }
.stage-badge--complete { background: #eaf4e5; color: #477a32; }
.wp-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.wp-chip { display: inline-flex; border-radius: 999px; padding: 3px 9px; font-size: 11px; font-weight: 700; background: #eef2f7; color: #2b3e58; }
.text-button { border: 0; padding: 4px; background: transparent; color: #304f7e; font-size: 12px; font-weight: 750; }
.timeline { display: grid; padding: 4px 20px 22px; }
.timeline-item { position: relative; display: grid; grid-template-columns: 20px 1fr; gap: 10px; padding: 14px 0; border-bottom: 1px solid #edf1f5; }
.timeline-item:last-child { border-bottom: 0; }
.timeline-dot { width: 10px; height: 10px; margin-top: 4px; border: 2px solid #304f7e; border-radius: 50%; background: #fff; }
.timeline-dot--change { border-color: #b8c3d1; }
.timeline-item strong { color: #2b3e58; font-size: 13px; }
.timeline-item p { margin: 4px 0; color: #65748a; font-size: 12px; }
.timeline-item small { color: #8b96a5; font-size: 10px; }
@media (max-width: 1100px) { .process-layout { grid-template-columns: 1fr; } }
@media (max-width: 900px) { .detail-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 520px) { .detail-grid { grid-template-columns: 1fr; } }
</style>
