<script setup lang="ts">
import Button from "~/components/ui/Button.vue";
import { computed, ref } from "vue";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  CircleOff,
  FileText,
  RotateCcw,
  ShieldCheck,
  UserRound,
} from "lucide-vue-next";

import type {
  RequirementGroup,
  RequirementWaiver,
  RequirementWaiverReasonCode,
} from "~/types/equipment";

import { formatDateTime } from "~/utils/format";
import { REQUIREMENT_WAIVER_REASON_LABELS } from "~/utils/workflow";
import SearchableSelect from "~/components/ui/SearchableSelect.vue";

const props = defineProps<{
  equipmentId: string;
  stage: number;
  group?: RequirementGroup | null;
  waiver?: RequirementWaiver | null;
}>();

const emit = defineEmits<{
  changed: [];
}>();

const auth = useAuthStore();
const api = useApi();

const canOperate = auth.can("workflow:transition");

const busy = ref(false);
const actionError = ref("");

const showWaiveModal = ref(false);
const reasonCode = ref<RequirementWaiverReasonCode>("OTHER");
const REASON_OPTIONS = Object.entries(REQUIREMENT_WAIVER_REASON_LABELS).map(([id, label]) => ({ id, label }));
const justification = ref("");

const showRevokeModal = ref(false);
const revokeReason = ref("");

const expanded = ref(false);

const label = computed(
  () => props.waiver?.requirementGroupLabel ?? props.group?.label ?? "",
);

const waiverReasonLabel = computed(() => {
  if (!props.waiver) return "";

  return REQUIREMENT_WAIVER_REASON_LABELS[props.waiver.reasonCode];
});

function openWaive(): void {
  reasonCode.value = "OTHER";
  justification.value = "";
  actionError.value = "";
  showWaiveModal.value = true;
}

async function confirmWaive(): Promise<void> {
  if (busy.value || !justification.value.trim() || !props.group) {
    return;
  }

  busy.value = true;
  actionError.value = "";

  try {
    await api.post(`/equipments/${props.equipmentId}/requirement-waivers`, {
      stage: props.stage,
      requirementGroupCode: props.group.code,
      reasonCode: reasonCode.value,
      justification: justification.value.trim(),
    });

    showWaiveModal.value = false;
    emit("changed");
  } catch (caught) {
    actionError.value =
      caught instanceof Error
        ? caught.message
        : "Não foi possível registrar a dispensa.";
  } finally {
    busy.value = false;
  }
}

function openRevoke(): void {
  revokeReason.value = "";
  actionError.value = "";
  showRevokeModal.value = true;
}

async function confirmRevoke(): Promise<void> {
  if (busy.value || !props.waiver) return;

  busy.value = true;
  actionError.value = "";

  try {
    await api.post(
      `/equipments/${props.equipmentId}/requirement-waivers/${props.waiver.id}/revoke`,
      {
        revokeReason: revokeReason.value.trim() || null,
      },
    );

    showRevokeModal.value = false;
    emit("changed");
  } catch (caught) {
    actionError.value =
      caught instanceof Error
        ? caught.message
        : "Não foi possível revogar a dispensa.";
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <section
    v-if="!waiver && group && group.status === 'MISSING' && group.waivable"
    class="requirement-card requirement-card--missing"
    data-testid="waiver-banner-missing"
  >
    <div class="requirement-icon requirement-icon--warning">
      <AlertTriangle :size="18" />
    </div>

    <div class="requirement-content">
      <div class="requirement-heading">
        <div>
          <span class="requirement-eyebrow"> Requisito pendente </span>

          <h4>{{ group.label }}</h4>
        </div>

        <span class="requirement-status requirement-status--warning">
          Necessário para avançar
        </span>
      </div>

      <p class="requirement-message">
        {{ group.message }}
      </p>

      <div v-if="canOperate" class="requirement-actions">
        <Button
          type="button"
          :data-testid="`waive-${group.code}`"
          variant="outline"
          size="sm"
          @click="openWaive"
        >
          <CircleOff :size="14" />
          Não possui {{ group.label.toLowerCase() }}
        </Button>
      </div>
    </div>
  </section>

  <section
    v-else-if="waiver"
    class="requirement-card requirement-card--waived"
    data-testid="waiver-banner-waived"
  >
    <div class="requirement-icon requirement-icon--success">
      <ShieldCheck :size="18" />
    </div>

    <div class="requirement-content">
      <div class="requirement-heading">
        <div>
          <span class="requirement-eyebrow"> Requisito dispensado </span>

          <h4>{{ waiver.requirementGroupLabel }}</h4>
        </div>

        <span class="requirement-status requirement-status--success">
          <CheckCircle2 :size="12" />
          Dispensado
        </span>
      </div>

      <div class="waiver-meta">
        <div class="waiver-meta-item">
          <FileText :size="13" />
          <div>
            <span class="waiver-meta-label">Motivo</span>
            <strong>{{ waiverReasonLabel }}</strong>
          </div>
        </div>

        <div class="waiver-meta-item">
          <UserRound :size="13" />
          <div>
            <span class="waiver-meta-label">Registrado por</span>
            <strong>
              {{ waiver.createdBy?.name ?? "Usuário removido" }}
            </strong>
          </div>
        </div>

        <div class="waiver-meta-item">
          <span class="meta-dot" />
          <div>
            <span class="waiver-meta-label">Data</span>
            <strong>{{ formatDateTime(waiver.createdAt) }}</strong>
          </div>
        </div>
      </div>

      <div class="waiver-bottom">
        <button
          type="button"
          class="justification-toggle"
          :aria-expanded="expanded"
          @click="expanded = !expanded"
        >
          <ChevronDown
            :size="14"
            :class="{ 'toggle-chevron--open': expanded }"
          />
          {{ expanded ? "Ocultar justificativa" : "Ver justificativa" }}
        </button>

        <Button

          v-if="canOperate"

          type="button"

          class="revoke-action"

          :data-testid="`revoke-waiver-${waiver.requirementGroupCode}`"

          variant="destructive"

          @click="openRevoke"

        >
          <RotateCcw :size="13" />
          Revogar dispensa
        </Button>
      </div>

      <Transition name="waiver-expand">
        <div v-if="expanded" class="waiver-justification">
          <span>Justificativa registrada</span>
          <p>{{ waiver.justification }}</p>
        </div>
      </Transition>
    </div>
  </section>

  <AppModal
    v-if="group"
    :open="showWaiveModal"
    :title="`Marcar ${label.toLowerCase()} como não existente`"
    @close="showWaiveModal = false"
  >
    <form class="waiver-form" @submit.prevent="confirmWaive">
      <div class="modal-guidance">
        <span class="modal-guidance-icon">
          <CircleOff :size="17" />
        </span>

        <div>
          <strong>Registrar dispensa do requisito</strong>
          <p>
            Esta ação não pula a fase. Ela registra que este requisito não
            existe para esta aquisição. O avanço continuará manualmente e os
            dados já preenchidos serão preservados.
          </p>
        </div>
      </div>

      <div class="field">
        <SearchableSelect
          :model-value="reasonCode"
          :options="REASON_OPTIONS"
          :sorted="false"
          :clearable="false"
          required
          label="Motivo *"
          placeholder="Buscar motivo"
          test-id="waiver-reason"
          @update:model-value="reasonCode = $event as RequirementWaiverReasonCode"
        />
      </div>

      <label class="field">
        <span>Justificativa *</span>
        <textarea
          v-model="justification"
          maxlength="1000"
          required
          rows="4"
          placeholder="Explique por que este requisito não se aplica a esta aquisição."
        />
      </label>

      <p v-if="actionError" class="notice error" role="alert">
        {{ actionError }}
      </p>

      <div class="form-actions">
        <Button
          type="button"
          :disabled="busy"
          variant="outline"
          @click="showWaiveModal = false"
        >
          Cancelar
        </Button>

        <Button

          type="submit"

          :disabled="!justification.trim() || busy"

          :loading="busy"

          variant="default"

        >
          {{ busy ? "Salvando..." : "Confirmar dispensa" }}
        </Button>
      </div>
    </form>
  </AppModal>

  <AppModal
    :open="showRevokeModal"
    title="Revogar dispensa"
    @close="showRevokeModal = false"
  >
    <form class="waiver-form" @submit.prevent="confirmRevoke">
      <div class="modal-guidance modal-guidance--danger">
        <span class="modal-guidance-icon">
          <RotateCcw :size="17" />
        </span>

        <div>
          <strong>O requisito voltará a ser obrigatório</strong>
          <p>
            Depois da revogação, este requisito voltará a ser exigido
            normalmente para avançar a fase.
          </p>
        </div>
      </div>

      <label class="field">
        <span>Motivo da revogação</span>
        <textarea
          v-model="revokeReason"
          maxlength="1000"
          rows="4"
          placeholder="Opcional: informe por que a dispensa está sendo revogada."
        />
      </label>

      <p v-if="actionError" class="notice error" role="alert">
        {{ actionError }}
      </p>

      <div class="form-actions">
        <Button
          type="button"
          :disabled="busy"
          variant="outline"
          @click="showRevokeModal = false"
        >
          Cancelar
        </Button>

        <Button type="submit" :disabled="busy" :loading="busy" variant="destructive">
          {{ busy ? "Salvando..." : "Revogar dispensa" }}
        </Button>
      </div>
    </form>
  </AppModal>
</template>

<style scoped>
.requirement-card {
  display: grid;
  grid-template-columns: 38px minmax(0, 1fr);
  gap: 14px;
  margin: 0 18px 14px;
  padding: 14px 16px;
  border: 1px solid #dde4ed;
  border-radius: 12px;
  background: #fff;
  box-shadow: 0 4px 14px rgb(29 48 76 / 4%);
}

.requirement-card--missing {
  border-color: #eadfcb;
  background: #fffcf7;
}

.requirement-card--waived {
  border-color: #d8e3ef;
  background: #fbfdff;
}

.requirement-icon {
  display: grid;
  width: 38px;
  height: 38px;
  place-items: center;
  border-radius: 9px;
}

.requirement-icon--warning {
  background: #fff2dc;
  color: #a46a1f;
}

.requirement-icon--success {
  background: #eaf2fb;
  color: #3b6595;
}

.requirement-content {
  display: grid;
  min-width: 0;
  gap: 12px;
}

.requirement-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
}

.requirement-heading > div:first-child {
  min-width: 0;
}

.requirement-eyebrow {
  display: block;
  margin-bottom: 4px;
  color: #56657a;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.03em;
  text-transform: uppercase;
}

.requirement-heading h4 {
  margin: 0;
  color: #213758;
  font-size: 14px;
  font-weight: 800;
  line-height: 1.3;
}

.requirement-status {
  display: inline-flex;
  flex: 0 0 auto;
  min-height: 24px;
  align-items: center;
  gap: 5px;
  padding: 0 9px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 750;
  white-space: nowrap;
}

.requirement-status--warning {
  border: 1px solid #ebd9b8;
  background: #fff6e7;
  color: #94611d;
}

.requirement-status--success {
  border: 1px solid #d4e2f1;
  background: #eef5fd;
  color: #3a6495;
}

.requirement-message {
  margin: 0;
  color: #66758a;
  font-size: 13px;
  line-height: 1.5;
}

.requirement-actions {
  display: flex;
  justify-content: flex-start;
}

.waiver-meta {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.waiver-meta-item {
  display: grid;
  grid-template-columns: 18px minmax(0, 1fr);
  gap: 7px;
  min-width: 0;
  align-items: flex-start;
  padding: 8px 9px;
  border: 1px solid #e5eaf0;
  border-radius: 9px;
  background: #fff;
  color: #708096;
}

.waiver-meta-item > svg,
.meta-dot {
  margin-top: 2px;
}

.meta-dot {
  width: 6px;
  height: 6px;
  margin-left: 4px;
  border-radius: 50%;
  background: #8ba0b8;
}

.waiver-meta-item > div {
  display: grid;
  min-width: 0;
  gap: 2px;
}

.waiver-meta-label {
  color: #56657a;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.03em;
  text-transform: uppercase;
}

.waiver-meta-item strong {
  overflow: hidden;
  color: #4d5f76;
  font-size: 12px;
  font-weight: 650;
  line-height: 1.4;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.waiver-bottom {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding-top: 2px;
}

.justification-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 2px;
  border: 0;
  background: transparent;
  font-family: inherit;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}

.justification-toggle {
  color: #304f7e;
}

.justification-toggle:hover {
  color: #233f68;
}

.justification-toggle svg {
  transition: transform 0.18s ease;
}

.toggle-chevron--open {
  transform: rotate(180deg);
}

.waiver-justification {
  display: grid;
  gap: 5px;
  padding: 10px 11px;
  border: 1px solid #e3e8ef;
  border-radius: 9px;
  background: #f7f9fc;
}

.waiver-justification > span {
  color: #56657a;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.03em;
  text-transform: uppercase;
}

.waiver-justification p {
  margin: 0;
  color: #4d5e74;
  font-size: 12.5px;
  line-height: 1.5;
  white-space: pre-wrap;
}

.waiver-expand-enter-active,
.waiver-expand-leave-active {
  transition:
    opacity 0.16s ease,
    transform 0.16s ease;
}

.waiver-expand-enter-from,
.waiver-expand-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

.waiver-form {
  display: grid;
  gap: 15px;
}

.modal-guidance {
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr);
  gap: 10px;
  padding: 11px;
  border: 1px solid #dce5ef;
  border-radius: 9px;
  background: #f6f9fc;
}

.modal-guidance--danger {
  border-color: #eadbd8;
  background: #fff9f8;
}

.modal-guidance-icon {
  display: grid;
  width: 34px;
  height: 34px;
  place-items: center;
  border-radius: 9px;
  background: #eaf2fb;
  color: #3f6795;
}

.modal-guidance--danger .modal-guidance-icon {
  background: #fbecea;
  color: #a4453a;
}

.modal-guidance > div {
  display: grid;
  gap: 3px;
}

.modal-guidance strong {
  color: #344a65;
  font-size: 12.5px;
  font-weight: 750;
}

.modal-guidance p {
  margin: 0;
  color: #708096;
  font-size: 12px;
  line-height: 1.5;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 9px;
  padding-top: 2px;
}

.danger-primary {
  border-color: #a4453a !important;
  background: #a4453a !important;
  color: #fff !important;
}

.danger-primary:hover:not(:disabled) {
  background: #923c33 !important;
}

@media (max-width: 760px) {
  .requirement-card {
    grid-template-columns: 34px minmax(0, 1fr);
    margin-left: 12px;
    margin-right: 12px;
  }

  .requirement-icon {
    width: 34px;
    height: 34px;
  }

  .requirement-heading {
    align-items: flex-start;
    flex-direction: column;
  }

  .waiver-meta {
    grid-template-columns: 1fr;
  }

  .waiver-meta-item strong {
    white-space: normal;
  }

  .waiver-bottom {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
