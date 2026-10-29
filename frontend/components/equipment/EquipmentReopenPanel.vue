<script setup lang="ts">
import { computed, ref } from "vue";
import { RotateCcw } from "lucide-vue-next";
import type { ReopenRequest } from "~/types/equipment";
import Button from "~/components/ui/Button.vue";
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
  <section class="surface">
    <div class="surface-header"><div><h2>Reabertura</h2><p>Solicitação de reabertura de fase, com aprovação por permissão superior.</p></div></div>
    <div class="surface-body">
      <template v-if="pendingReopenRequest">
        <p class="reopen-pending" data-testid="pending-reopen-request">
          Reabertura para <strong>{{ pendingReopenRequest.targetStage }} · {{ pendingReopenRequest.targetStageLabel }}</strong>
          solicitada por {{ pendingReopenRequest.requestedBy?.name ?? "usuário removido" }}
          em {{ formatDateTime(pendingReopenRequest.requestedAt) }} — aguardando aprovação.
          <br><em>{{ pendingReopenRequest.justification }}</em>
        </p>
        <div v-if="canApproveReopen" class="reopen-decision-actions">
          <Button variant="default" data-testid="approve-reopen" @click="openReopenDecision('approve')">Aprovar</Button>
          <Button variant="destructive" data-testid="reject-reopen" @click="openReopenDecision('reject')">Rejeitar</Button>
        </div>
      </template>
      <Button
        v-else-if="canRequestReopen && currentStage >= 1 && isActive"
        variant="outline"
        data-testid="request-reopen-button"
        @click="openReopenRequest"
      >
        <RotateCcw :size="15" /> Solicitar reabertura
      </Button>
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
      <p v-if="actionError" class="notice error" role="alert">{{ actionError }}</p>
      <div class="form-actions">
        <Button variant="outline" @click="showReopenRequest = false">Cancelar</Button>
        <Button
          type="submit"
          variant="default"
          :loading="busy"
          :disabled="reopenTargetStage === '' || !reopenJustification.trim()"
        >
          {{ busy ? "Enviando..." : "Solicitar" }}
        </Button>
      </div>
    </form>
  </AppModal>

  <AppModal :open="showReopenDecision" :title="reopenDecisionMode === 'approve' ? 'Aprovar reabertura' : 'Rejeitar reabertura'" @close="showReopenDecision = false">
    <form class="exception-form" @submit.prevent="confirmReopenDecision">
      <label class="field"><span>Nota (opcional)</span><textarea v-model="reopenDecisionNote" maxlength="1000" rows="3" /></label>
      <p v-if="actionError" class="notice error" role="alert">{{ actionError }}</p>
      <div class="form-actions">
        <Button variant="outline" @click="showReopenDecision = false">Cancelar</Button>
        <Button type="submit" variant="default" :loading="busy">
          {{ reopenDecisionMode === "approve" ? "Confirmar aprovação" : "Confirmar rejeição" }}
        </Button>
      </div>
    </form>
  </AppModal>
</template>

<style scoped>
.operational-hint { margin: 0; color: #8b96a5; font-size: 12px; }
.exception-form { display: grid; gap: 14px; }
.exception-hint { margin: -6px 0 0; color: #8b96a5; font-size: 11.5px; }
.reopen-pending { margin: 0 0 12px; color: #65748a; font-size: 12px; }
.reopen-decision-actions { display: flex; gap: 9px; }
.form-actions { display: flex; justify-content: flex-end; gap: 9px; }
</style>
