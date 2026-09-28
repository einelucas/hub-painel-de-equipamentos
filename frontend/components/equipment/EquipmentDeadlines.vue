<script setup lang="ts">
import type { EquipmentCalculated } from "~/types/equipment";
import { formatDateOnly } from "~/utils/format";
import { negotiationStatusLabel, negotiationStatusTone } from "~/utils/negotiationStatus";
import { workNeedStatusLabel, workNeedStatusTone } from "~/utils/workNeedStatus";

/**
 * Seção "Prazos e planejamento" — só apresentação dos valores calculados
 * pelo backend a partir dos componentes (FUN-001). Nenhum prazo é
 * recalculado aqui; o Vue só formata e rotula o que já vem pronto em
 * `equipment.calculated`.
 */
defineProps<{ calculated: EquipmentCalculated }>();
</script>

<template>
  <section class="surface">
    <div class="surface-header">
      <div>
        <h2>Prazos e planejamento</h2>
        <p>Derivado dos componentes (FUN-001) — só leitura; recalculado a cada mudança nos componentes.</p>
      </div>
    </div>
    <div class="surface-body detail-grid">
      <div class="detail-field"><span>Lead time máximo</span><strong>{{ calculated.maxLeadTimeDays === null ? "—" : `${calculated.maxLeadTimeDays} dias` }}</strong></div>
      <div class="detail-field"><span>Dias antes do startup (máx.)</span><strong>{{ calculated.maxPreStartDays === null ? "—" : `${calculated.maxPreStartDays} dias` }}</strong></div>
      <div class="detail-field"><span>Frete máximo</span><strong>{{ calculated.maxFreightDays === null ? "—" : `${calculated.maxFreightDays} dias` }}</strong></div>
      <div class="detail-field"><span>Limite entrega em obra</span><strong>{{ formatDateOnly(calculated.deliveryDeadline) }}</strong></div>
      <div class="detail-field">
        <span>Status necessidade da obra</span>
        <strong>
          <span
            class="negotiation-badge"
            :class="workNeedStatusTone(calculated.workNeedStatus)"
            data-testid="work-need-status-badge"
          >{{ workNeedStatusLabel(calculated.workNeedStatus) }}</span>
        </strong>
      </div>
      <div class="detail-field"><span>Limite contrato/OC</span><strong>{{ formatDateOnly(calculated.contractOrderDeadline) }}</strong></div>
      <div class="detail-field">
        <span>Limite negociação</span>
        <strong>
          {{ formatDateOnly(calculated.negotiationDeadline) }}
          <template v-if="calculated.negotiationDaysRemaining !== null">
            ({{ calculated.negotiationDaysRemaining >= 0 ? `${calculated.negotiationDaysRemaining} dias restantes` : `${Math.abs(calculated.negotiationDaysRemaining)} dias em atraso` }})
          </template>
        </strong>
      </div>
      <div class="detail-field">
        <span>Status negociação</span>
        <strong>
          <span
            class="negotiation-badge"
            :class="negotiationStatusTone(calculated.negotiationStatus)"
            data-testid="negotiation-status-badge"
          >{{ negotiationStatusLabel(calculated.negotiationStatus) }}</span>
        </strong>
      </div>
    </div>
  </section>
</template>

<style scoped>
.detail-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 22px 18px; }
.detail-field { display: grid; align-content: start; gap: 5px; }
.detail-field > span { color: #7a879a; font-size: 10px; font-weight: 800; letter-spacing: .05em; text-transform: uppercase; }
.detail-field strong { color: #2b3e58; font-size: 13px; font-weight: 700; }
.negotiation-badge { display: inline-flex; border-radius: 999px; padding: 4px 10px; font-size: 11px; font-weight: 750; }
.negotiation-badge--neutral { background: #eef2f7; color: #53647a; }
.negotiation-badge--complete { background: #eaf4e5; color: #477a32; }
.negotiation-badge--ok { background: #e8f1fc; color: #2f5f9c; }
.negotiation-badge--warning { background: #fff3df; color: #9b6418; }
.negotiation-badge--danger { background: #fbe8e8; color: #a53f3f; }
@media (max-width: 900px) { .detail-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 520px) { .detail-grid { grid-template-columns: 1fr; } }
</style>
