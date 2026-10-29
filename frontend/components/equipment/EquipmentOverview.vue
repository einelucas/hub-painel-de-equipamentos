<script setup lang="ts">
import { mdiPencilOutline } from "@mdi/js";
import { VBtn } from "vuetify/components";
import { computed } from "vue";
import type { Equipment, OperationalStatus, OperationalStatusEvent } from "~/types/equipment";
import { formatCurrency, formatDateOnly, formatDateTime } from "~/utils/format";
import { stageBadgeStyle } from "~/utils/stages";
import { OPERATIONAL_STATUS_LABELS } from "~/utils/workflow";
import { equipmentLocationLabel } from "~/utils/equipmentLocation";
import WorkPackageChips from "~/components/equipment/WorkPackageChips.vue";
import DisciplineBadge from "~/components/equipment/DisciplineBadge.vue";
import CriticalityBadge from "~/components/equipment/CriticalityBadge.vue";

/**
 * Seção "Resumo" do detalhe do equipamento — identificação, badges de
 * etapa/estado operacional, stepper do workflow e nota de estado. Só
 * apresentação: busca de dados, estado do workflow e o modal de edição
 * continuam na página `[id].vue`.
 */
const props = defineProps<{
  equipment: Equipment;
  currentStage: number;
  currentStageLabel: string;
  /** Data em que a etapa atual começou; `null` quando não há marco conhecido. */
  stageEnteredAt?: string | null;
  operationalStatus: OperationalStatus;
  lastOperationalEvent: OperationalStatusEvent | null;
  nextStageBlocked: boolean;
  canEdit: boolean;
}>();
const emit = defineEmits<{ edit: [] }>();

const isActive = computed(() => props.operationalStatus === "ACTIVE");
const stageStyle = computed(() => stageBadgeStyle(props.currentStage, props.currentStageLabel));
</script>

<template>
  <section class="surface">
    <div class="surface-header"><div><h2>Resumo</h2><p>Identificação e posição atual no processo.</p></div><VBtn v-if="canEdit"  variant="outlined" :prepend-icon="mdiPencilOutline" @click="emit('edit')"> Editar</VBtn></div>
    <div class="surface-body detail-grid">
      <div class="detail-field"><span>Unidade</span><strong>{{ equipment.unit.name }}</strong></div>
      <div class="detail-field"><span>Obra</span><strong>{{ equipment.projectContext.code ? `${equipment.projectContext.code} · ${equipment.projectContext.name}` : equipment.projectContext.name }}</strong></div>
      <div class="detail-field"><span>Área</span><strong data-testid="equipment-location">{{ equipmentLocationLabel(equipment) ?? "—" }}</strong></div>
      <div class="detail-field"><span>Disciplina</span><strong><DisciplineBadge v-if="equipment.discipline" :discipline="equipment.discipline" /><template v-else>—</template></strong></div>
      <div class="detail-field">
        <span>Work Packages</span>
        <WorkPackageChips
          :items="equipment.workPackages"
          :max-visible="equipment.workPackages.length"
        />
      </div>
      <div class="detail-field"><span>Responsável</span><strong>{{ equipment.responsibleUser?.name ?? "—" }}</strong></div>
      <div class="detail-field"><span>Fornecedor</span><strong>{{ equipment.supplier?.name ?? "—" }}</strong></div>
      <div class="detail-field"><span>Etapa atual</span><strong><span class="stage-badge" :style="stageStyle" data-testid="current-stage">{{ currentStage }} · {{ currentStageLabel }}</span></strong></div>
      <div class="detail-field">
        <span>Estado operacional</span>
        <strong>
          <span class="operational-badge" :class="`operational-badge--${operationalStatus.toLowerCase()}`" data-testid="operational-status-badge">
            {{ OPERATIONAL_STATUS_LABELS[operationalStatus] }}
          </span>
        </strong>
      </div>
      <div class="detail-field"><span>Startup</span><strong>{{ formatDateOnly(equipment.startupAt) }}</strong></div>
      <div class="detail-field"><span>Criticidade</span><strong><CriticalityBadge v-if="equipment.criticalityLabel || equipment.criticality" :label="equipment.criticalityLabel?.name ?? equipment.criticality!" :color="equipment.criticalityLabel?.color" /><template v-else>—</template></strong></div>
      <div class="detail-field"><span>CAPEX estimado</span><strong>{{ formatCurrency(equipment.capexEstimated) }}</strong></div>
      <div class="detail-field"><span>Valor total do projeto</span><strong>{{ formatCurrency(equipment.projectTotalValue) }}</strong></div>
      <div class="detail-field">
        <span>Entrega contratual</span>
        <strong>
          <template v-if="equipment.contractualDeliveryStart || equipment.contractualDeliveryEnd">
            {{ formatDateOnly(equipment.contractualDeliveryStart) }} — {{ formatDateOnly(equipment.contractualDeliveryEnd) }}
          </template>
          <template v-else>—</template>
        </strong>
      </div>
      <!-- Origem fecha a grade na 4ª linha, ao lado de Entrega contratual e
           abaixo de Criticidade — sem deslocar a sequência já conhecida. -->
      <div class="detail-field"><span>Origem</span><strong>{{ equipment.origin?.trim() || "—" }}</strong></div>
    </div>
    <EquipmentWorkflowStepper
      :current-stage="currentStage"
      :stage-entered-at="stageEnteredAt"
      :next-stage-blocked="nextStageBlocked"
    />
    <p v-if="!isActive && lastOperationalEvent" class="operational-note" data-testid="operational-note">
      <strong>{{ OPERATIONAL_STATUS_LABELS[operationalStatus] }}</strong> desde {{ formatDateTime(lastOperationalEvent.occurredAt) }}
      por {{ lastOperationalEvent.actor?.name ?? "usuário removido" }} — {{ lastOperationalEvent.justification }}
    </p>
  </section>
</template>

<style scoped>
.detail-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 22px 18px; }
.detail-field { display: grid; align-content: start; gap: 5px; }
.detail-field > span { color: #7a879a; font-size: 10px; font-weight: 800; letter-spacing: .05em; text-transform: uppercase; }
.detail-field strong { color: #2b3e58; font-size: 13px; font-weight: 700; }
.stage-badge { display: inline-flex; border-radius: 999px; padding: 4px 8px; font-size: 11px; font-weight: 750; }
.operational-badge { display: inline-flex; border-radius: 999px; padding: 4px 10px; font-size: 11px; font-weight: 750; }
.operational-badge--active { background: #eaf4e5; color: #477a32; }
.operational-badge--standby { background: #fff3df; color: #9b6418; }
.operational-badge--cancelled { background: #fbe8e8; color: #a53f3f; }
.operational-badge--in_sanitation { background: #e8f1fc; color: #2f5f9c; }
.operational-note { margin: 0 20px 16px; padding: 9px 12px; border-radius: 8px; background: #fafbfc; border: 1px solid #edf1f5; color: #65748a; font-size: 12px; }
@media (max-width: 900px) { .detail-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 520px) { .detail-grid { grid-template-columns: 1fr; } }
</style>
