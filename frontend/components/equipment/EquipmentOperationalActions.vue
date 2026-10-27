<script setup lang="ts">
import Button from "~/components/ui/Button.vue";
import { computed, ref } from "vue";
import { Ban, Pause, Play, RotateCcw, Wrench } from "lucide-vue-next";
import type { OperationalStatus } from "~/types/equipment";

const props = defineProps<{
  operationalStatus: OperationalStatus;
  canOperate: boolean;
  busy: boolean;
  actionError: string;

  enterStandby: (justification: string) => Promise<unknown>;
  liftStandby: (justification: string) => Promise<unknown>;
  cancelEquipment: (justification: string) => Promise<unknown>;
  enterSanitation: (justification: string) => Promise<unknown>;
  endSanitation: (justification: string) => Promise<unknown>;
}>();

const isActive = computed(() => props.operationalStatus === "ACTIVE");

const showStandby = ref(false);
const showLiftStandby = ref(false);
const showCancel = ref(false);
const showSanitation = ref(false);
const showEndSanitation = ref(false);

async function confirmStandby(text: string): Promise<void> {
  if (await props.enterStandby(text)) {
    showStandby.value = false;
  }
}

async function confirmLiftStandby(text: string): Promise<void> {
  if ((await props.liftStandby(text)) !== null) {
    showLiftStandby.value = false;
  }
}

async function confirmCancel(text: string): Promise<void> {
  if (await props.cancelEquipment(text)) {
    showCancel.value = false;
  }
}

async function confirmSanitation(text: string): Promise<void> {
  if (await props.enterSanitation(text)) {
    showSanitation.value = false;
  }
}

async function confirmEndSanitation(text: string): Promise<void> {
  if ((await props.endSanitation(text)) !== null) {
    showEndSanitation.value = false;
  }
}
</script>

<template>
  <section v-if="canOperate" class="surface process-actions">
    <div class="surface-header">
      <div>
        <h2>Ações do processo</h2>

        <p>
          Ações excepcionais do equipamento. Todas as alterações são
          justificadas e registradas no histórico.
        </p>
      </div>
    </div>

    <div class="surface-body" :aria-busy="busy">
      <p v-if="busy" class="busy-hint" role="status">
        <span class="spinner-small" aria-hidden="true" /> Processando ação...
      </p>
      <!-- Estado normal -->
      <div v-if="isActive" class="actions-row">
        <div class="actions-main">
          <Button
            class="action-button"
            type="button"
            :disabled="busy"
            data-testid="standby-button"
            variant="outline"
            @click="showStandby = true"
          >
            <Pause :size="16" :stroke-width="1.8" />
            <span>Colocar em Standby</span>
          </Button>

          <Button

            class="action-button"

            type="button"

            :disabled="busy"

            data-testid="sanitation-button"

            variant="outline"

            @click="showSanitation = true"

          >
            <Wrench :size="16" :stroke-width="1.8" />
            <span>Colocar em Saneamento</span>
          </Button>
        </div>

        <Button

          class="action-button action-button--danger"

          type="button"

          :disabled="busy"

          data-testid="cancel-button"

          variant="destructive"

          @click="showCancel = true"

        >
          <Ban :size="16" :stroke-width="1.8" />
          <span>Cancelar equipamento</span>
        </Button>
      </div>

      <!-- Standby -->
      <div v-else-if="operationalStatus === 'STANDBY'" class="status-action">
        <div class="status-action__text">
          <strong>Equipamento em Standby</strong>
          <span> O processo está pausado na etapa atual. </span>
        </div>

        <Button

          class="action-button action-button--primary"

          type="button"

          :disabled="busy"

          data-testid="lift-standby-button"

          variant="default"

          @click="showLiftStandby = true"

        >
          <Play :size="16" :stroke-width="1.8" />
          <span>Retomar processo</span>
        </Button>
      </div>

      <!-- Saneamento -->
      <div
        v-else-if="operationalStatus === 'IN_SANITATION'"
        class="status-action"
      >
        <div class="status-action__text">
          <strong>Equipamento em Saneamento</strong>
          <span>
            O processo permanece na fase 0 até a conclusão dos ajustes.
          </span>
        </div>

        <Button

          class="action-button action-button--primary"

          type="button"

          :disabled="busy"

          data-testid="end-sanitation-button"

          variant="default"

          @click="showEndSanitation = true"

        >
          <RotateCcw :size="16" :stroke-width="1.8" />
          <span>Encerrar saneamento</span>
        </Button>
      </div>

      <!-- Cancelado -->
      <div
        v-else-if="operationalStatus === 'CANCELLED'"
        class="cancelled-state"
      >
        <Ban :size="17" :stroke-width="1.8" />

        <div>
          <strong>Equipamento cancelado</strong>
          <span> O fluxo normal não pode ser retomado. </span>
        </div>
      </div>
    </div>

    <JustificationModal
      :open="showStandby"
      title="Colocar em Standby"
      message="O processo fica pausado na fase atual até o Standby ser removido."
      required
      :busy="busy"
      :error="actionError"
      confirm-label="Confirmar Standby"
      @confirm="confirmStandby"
      @close="showStandby = false"
    />

    <JustificationModal
      :open="showLiftStandby"
      title="Retomar processo"
      message="O equipamento volta a ficar ativo na mesma fase em que estava."
      :busy="busy"
      :error="actionError"
      confirm-label="Retomar processo"
      @confirm="confirmLiftStandby"
      @close="showLiftStandby = false"
    />

    <JustificationModal
      :open="showCancel"
      title="Cancelar equipamento"
      message="Ação definitiva: o cancelamento fica registrado na fase atual e não é possível retomar o fluxo normal depois."
      required
      :busy="busy"
      :error="actionError"
      confirm-label="Confirmar cancelamento"
      @confirm="confirmCancel"
      @close="showCancel = false"
    />

    <JustificationModal
      :open="showSanitation"
      title="Colocar em Saneamento"
      message="O equipamento volta para a fase 0 · Nova Demanda e fica marcado como Em Saneamento até ser encerrado."
      required
      :busy="busy"
      :error="actionError"
      confirm-label="Confirmar Saneamento"
      @confirm="confirmSanitation"
      @close="showSanitation = false"
    />

    <JustificationModal
      :open="showEndSanitation"
      title="Encerrar Saneamento"
      message="O equipamento volta a ficar ativo, permanecendo na fase 0 · Nova Demanda."
      :busy="busy"
      :error="actionError"
      confirm-label="Encerrar Saneamento"
      @confirm="confirmEndSanitation"
      @close="showEndSanitation = false"
    />
  </section>
</template>

<style scoped>
.process-actions .surface-header {
  padding: 20px 24px;
}

.process-actions .surface-header h2 {
  margin: 0;
  color: #1d3555;
  font-size: 17px;
  font-weight: 750;
}

.process-actions .surface-header p {
  margin: 5px 0 0;
  color: #7d8998;
  font-size: 12px;
  line-height: 1.45;
}

.process-actions .surface-body {
  padding: 18px 24px;
}

/* Linha principal */

.actions-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
}

.actions-main {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

/* Estado operacional */

.status-action {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
}

.status-action__text {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.status-action__text strong {
  color: #263d5a;
  font-size: 12px;
  font-weight: 700;
}

.status-action__text span {
  color: #84909f;
  font-size: 11px;
}

/* Cancelado */

.cancelled-state {
  display: flex;
  align-items: center;
  gap: 10px;

  color: #a4453a;
}

.cancelled-state div {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.cancelled-state strong {
  font-size: 12px;
  font-weight: 700;
}

.cancelled-state span {
  color: #8b96a5;
  font-size: 11px;
}

@media (max-width: 760px) {
  .actions-row,
  .status-action {
    align-items: stretch;
    flex-direction: column;
  }

  .actions-main {
    flex-direction: column;
  }
}
.busy-hint { display: flex; align-items: center; gap: 8px; margin: 0 0 10px; color: #65748a; font-size: 12px; }
</style>
