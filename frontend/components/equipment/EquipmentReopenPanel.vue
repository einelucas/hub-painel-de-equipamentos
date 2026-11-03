<script setup lang="ts">
import {
  mdiAccountOutline,
  mdiCalendarClockOutline,
  mdiMessageTextOutline,
  mdiRestore,
} from "@mdi/js";
import { computed, ref } from "vue";
import type { ReopenRequest } from "~/types/equipment";
import { VBtn, VIcon } from "vuetify/components";
import { formatDateTime } from "~/utils/format";
import { STAGE_OPTIONS } from "~/utils/selectOptions";
import SearchableSelect from "~/components/ui/SearchableSelect.vue";

/**
 * Seção "Reabertura" (Etapa 7C) — solicitação de reabertura de fase, com
 * aprovação por permissão superior. Só apresentação + estado local dos
 * modais: as operações em si (chamada de API, recarregar o workflow)
 * continuam em `useEquipmentWorkflow`, injetadas aqui como props tipadas.
 */
const props = defineProps<{
  currentStage: number;
  isActive: boolean;
  canRequestReopen: boolean;
  canApproveReopen: boolean;
  pendingReopenRequest: ReopenRequest | null;
  busy: boolean;
  actionError: string;
  requestReopen: (targetStage: number, justification: string) => Promise<unknown>;
  approveReopen: (requestId: string, note: string) => Promise<unknown>;
  rejectReopen: (requestId: string, note: string) => Promise<unknown>;
}>();
/** Emitido só após aprovar/rejeitar com sucesso — a fase atual do
 * equipamento muda, e a página recarrega o equipamento inteiro (não só o
 * workflow), igual ao comportamento original de `confirmReopenDecision`.
 * Solicitar reabertura não muda a fase, então não precisa disso. */
const emit = defineEmits<{ decided: [] }>();

const showReopenRequest = ref(false);
const reopenTargetStage = ref<number | "">("");
const reopenJustification = ref("");
const reopenStageOptions = computed(() =>
  STAGE_OPTIONS.filter((_, index) => index < props.currentStage),
);

function openReopenRequest(): void {
  reopenTargetStage.value = "";
  reopenJustification.value = "";
  showReopenRequest.value = true;
}
async function confirmReopenRequest(): Promise<void> {
  if (props.busy) return;
  if (reopenTargetStage.value === "" || !reopenJustification.value.trim()) return;
  if (await props.requestReopen(Number(reopenTargetStage.value), reopenJustification.value.trim())) {
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
  const request = props.pendingReopenRequest;
  if (!request || props.busy) return;
  const action = reopenDecisionMode.value === "approve" ? props.approveReopen : props.rejectReopen;
  if (await action(request.id, reopenDecisionNote.value.trim())) {
    showReopenDecision.value = false;
    emit("decided");
  }
}
</script>

<template>
  <section
    id="reabertura"
    class="surface reopen-surface"
    :class="{ 'reopen-surface--pending': pendingReopenRequest }"
  >
    <div class="surface-header reopen-header">
      <div class="reopen-title">
        <span class="reopen-title-icon" aria-hidden="true">
          <VIcon :icon="mdiRestore" size="20" />
        </span>
        <div>
          <h2>Reabertura</h2>
          <p>Solicitação de reabertura de fase, com aprovação por permissão superior.</p>
        </div>
      </div>
      <span v-if="pendingReopenRequest" class="reopen-status">
        <span class="reopen-status-dot" aria-hidden="true" />
        Aguardando aprovação
      </span>
    </div>
    <div class="surface-body">
      <template v-if="pendingReopenRequest">
        <article
          class="reopen-pending"
          data-testid="pending-reopen-request"
          aria-label="Solicitação de reabertura aguardando aprovação"
        >
          <div class="reopen-target">
            <span class="reopen-eyebrow">Retorno solicitado para</span>
            <h3>
              <span>{{ pendingReopenRequest.targetStage }}</span>
              {{ pendingReopenRequest.targetStageLabel }}
            </h3>
          </div>

          <dl class="reopen-meta">
            <div class="reopen-meta-item">
              <VIcon :icon="mdiAccountOutline" size="17" aria-hidden="true" />
              <div>
                <dt>Solicitado por</dt>
                <dd>{{ pendingReopenRequest.requestedBy?.name ?? "Usuário removido" }}</dd>
              </div>
            </div>
            <div class="reopen-meta-item">
              <VIcon :icon="mdiCalendarClockOutline" size="17" aria-hidden="true" />
              <div>
                <dt>Solicitado em</dt>
                <dd>{{ formatDateTime(pendingReopenRequest.requestedAt) }}</dd>
              </div>
            </div>
          </dl>

          <div class="reopen-justification">
            <VIcon :icon="mdiMessageTextOutline" size="19" aria-hidden="true" />
            <div>
              <span>Justificativa da solicitação</span>
              <p>{{ pendingReopenRequest.justification }}</p>
            </div>
          </div>

          <div v-if="canApproveReopen" class="reopen-decision">
            <span>Decisão da solicitação</span>
            <div class="reopen-decision-actions">
              <VBtn
                variant="flat"
                color="success"
                data-testid="approve-reopen"
                @click="openReopenDecision('approve')"
              >
                Aprovar reabertura
              </VBtn>
              <VBtn
                variant="outlined"
                color="error"
                data-testid="reject-reopen"
                @click="openReopenDecision('reject')"
              >
                Rejeitar
              </VBtn>
            </div>
          </div>
        </article>
      </template>
      <VBtn
        v-else-if="canRequestReopen && currentStage >= 1 && isActive"
        variant="outlined"
        color="secondary"
        data-testid="request-reopen-button"
        :prepend-icon="mdiRestore"
       @click="openReopenRequest">
         Solicitar reabertura
      </VBtn>
      <p v-else-if="currentStage < 1" class="operational-hint">Não há fase anterior para reabrir.</p>
    </div>
  </section>

  <AppModal :open="showReopenRequest" title="Solicitar reabertura" @close="showReopenRequest = false">
    <form class="exception-form" @submit.prevent="confirmReopenRequest">
      <div class="field">
        <SearchableSelect
          :model-value="String(reopenTargetStage)"
          :options="reopenStageOptions"
          :sorted="false"
          :clearable="false"
          required
          label="Fase de destino *"
          placeholder="Buscar fase"
          empty-label="Selecione"
          test-id="reopen-target-stage"
          @update:model-value="reopenTargetStage = $event === '' ? '' : Number($event)"
        />
      </div>
      <p class="exception-hint">O equipamento permanece na fase atual até a solicitação ser aprovada por um usuário com permissão de aprovação.</p>
      <label class="field">
        <span>Justificativa *</span>
        <textarea v-model="reopenJustification" maxlength="1000" required rows="3" />
      </label>
      <VAlert v-if="actionError" type="error" role="alert">{{ actionError }}</VAlert>
      <div class="form-actions">
        <VBtn variant="outlined" @click="showReopenRequest = false">Cancelar</VBtn>
        <VBtn
          type="submit"
          variant="tonal"
          color="primary"
          :loading="busy"
          :disabled="reopenTargetStage === '' || !reopenJustification.trim()"
        >
          {{ busy ? "Enviando..." : "Solicitar" }}
        </VBtn>
      </div>
    </form>
  </AppModal>

  <AppModal :open="showReopenDecision" :title="reopenDecisionMode === 'approve' ? 'Aprovar reabertura' : 'Rejeitar reabertura'" @close="showReopenDecision = false">
    <form class="exception-form" @submit.prevent="confirmReopenDecision">
      <label class="field"><span>Nota (opcional)</span><textarea v-model="reopenDecisionNote" maxlength="1000" rows="3" /></label>
      <VAlert v-if="actionError" type="error" role="alert">{{ actionError }}</VAlert>
      <div class="form-actions">
        <VBtn variant="outlined" @click="showReopenDecision = false">Cancelar</VBtn>
        <VBtn
          type="submit"
          variant="tonal"
          :color="reopenDecisionMode === 'approve' ? 'success' : 'error'"
          :loading="busy"
          :disabled="busy"
        >
          {{ reopenDecisionMode === "approve" ? "Confirmar aprovação" : "Confirmar rejeição" }}
        </VBtn>
      </div>
    </form>
  </AppModal>
</template>

<style scoped>
.operational-hint { margin: 0; color: #8b96a5; font-size: 12px; }
.exception-form { display: grid; gap: 14px; }
.exception-hint { margin: -6px 0 0; color: #8b96a5; font-size: 11.5px; }
.form-actions { display: flex; justify-content: flex-end; gap: 9px; }

.reopen-surface--pending {
  border-color: #ead8b7;
  box-shadow: 0 10px 32px rgb(120 80 22 / 9%);
}

.reopen-surface--pending .reopen-header {
  border-bottom-color: #eddfc6;
  background: linear-gradient(90deg, #fffaf1 0%, #fff 58%);
}

.reopen-title {
  display: flex;
  min-width: 0;
  align-items: flex-start;
  gap: 12px;
}

.reopen-title-icon {
  display: grid;
  width: 38px;
  height: 38px;
  flex: 0 0 38px;
  place-items: center;
  border-radius: 10px;
  background: #eef3f9;
  color: #304f7e;
}

.reopen-surface--pending .reopen-title-icon {
  background: #fff0d7;
  color: #9a6218;
}

.reopen-status {
  display: inline-flex;
  min-height: 28px;
  align-items: center;
  gap: 7px;
  padding: 0 11px;
  border: 1px solid #e6d1aa;
  border-radius: 999px;
  background: #fff5e4;
  color: #8b5814;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.02em;
  white-space: nowrap;
}

.reopen-status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #d88920;
  box-shadow: 0 0 0 3px rgb(234 162 57 / 17%);
}

.reopen-pending {
  display: grid;
  gap: 18px;
}

.reopen-target {
  display: grid;
  gap: 5px;
}

.reopen-eyebrow {
  color: #8b641f;
  font-size: 10.5px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.reopen-target h3 {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 0;
  color: #213758;
  font-size: 17px;
  font-weight: 800;
  line-height: 1.35;
}

.reopen-target h3 span {
  display: grid;
  width: 30px;
  height: 30px;
  flex: 0 0 30px;
  place-items: center;
  border-radius: 8px;
  background: #304f7e;
  color: #fff;
  font-size: 13px;
}

.reopen-meta {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin: 0;
}

.reopen-meta-item {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 10px;
  padding: 11px 12px;
  border: 1px solid #e5eaf1;
  border-radius: 10px;
  background: #fafbfd;
  color: #607087;
}

.reopen-meta-item > .v-icon {
  flex: 0 0 auto;
  color: #506987;
}

.reopen-meta-item dt {
  margin: 0 0 2px;
  color: #7c899a;
  font-size: 10.5px;
  font-weight: 700;
}

.reopen-meta-item dd {
  overflow: hidden;
  margin: 0;
  color: #2d405e;
  font-size: 12.5px;
  font-weight: 750;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.reopen-justification {
  display: grid;
  grid-template-columns: 24px minmax(0, 1fr);
  gap: 11px;
  padding: 14px 15px;
  border: 1px solid #e7d6b6;
  border-left: 4px solid #eaa239;
  border-radius: 10px;
  background: #fffbf4;
  color: #885a19;
}

.reopen-justification > .v-icon {
  margin-top: 1px;
}

.reopen-justification span {
  display: block;
  margin-bottom: 4px;
  color: #8b641f;
  font-size: 10.5px;
  font-weight: 800;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.reopen-justification p {
  margin: 0;
  color: #334864;
  font-size: 13px;
  font-weight: 600;
  line-height: 1.55;
}

.reopen-decision {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding-top: 16px;
  border-top: 1px solid #e8edf3;
}

.reopen-decision > span {
  color: #66758a;
  font-size: 11px;
  font-weight: 750;
}

.reopen-decision-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 9px;
}

@media (max-width: 700px) {
  .reopen-header,
  .reopen-decision {
    align-items: stretch;
    flex-direction: column;
  }

  .reopen-status {
    align-self: flex-start;
  }

  .reopen-meta {
    grid-template-columns: 1fr;
  }

  .reopen-decision-actions {
    justify-content: stretch;
  }

  .reopen-decision-actions .v-btn {
    flex: 1 1 160px;
  }
}
</style>
