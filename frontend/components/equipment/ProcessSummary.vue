<script setup lang="ts">
import { computed } from "vue";
import type { EquipmentProcesses } from "~/types/equipment";
import { formatCurrency, formatDate } from "~/utils/format";

const props = defineProps<{ processes: EquipmentProcesses }>();

function bool(value: boolean): string {
  return value ? "Sim" : "Não";
}

function text(value: string | null): string {
  return value && value.trim() !== "" ? value : "—";
}

const groups = computed(() => [
  {
    title: "Negociação",
    fields: [
      { label: "Equalizada", value: bool(props.processes.negotiation.equalized) },
      { label: "Data da negociação", value: formatDate(props.processes.negotiation.negotiatedAt) },
    ],
  },
  {
    title: "Jurídico",
    fields: [
      { label: "Abertura", value: formatDate(props.processes.legal.openedAt) },
      { label: "Chamado", value: text(props.processes.legal.ticketNumber) },
      { label: "Minuta elaborada", value: bool(props.processes.legal.draftPrepared) },
      { label: "Minuta aprovada", value: bool(props.processes.legal.draftApproved) },
    ],
  },
  {
    title: "Contrato",
    fields: [
      { label: "Número", value: text(props.processes.contract.contractNumber) },
      { label: "Escrituração", value: formatDate(props.processes.contract.executedAt) },
      { label: "Entrega contratual", value: formatDate(props.processes.contract.deliveryAt) },
    ],
  },
  {
    title: "SC / OCI",
    fields: [
      { label: "Tipo", value: text(props.processes.purchaseRequest.kind) },
      { label: "Número", value: text(props.processes.purchaseRequest.requestNumber) },
      { label: "Data", value: formatDate(props.processes.purchaseRequest.requestedAt) },
    ],
  },
  {
    title: "Ordem de compra",
    fields: [
      { label: "Número", value: text(props.processes.purchaseOrder.orderNumber) },
      { label: "Data", value: formatDate(props.processes.purchaseOrder.orderedAt) },
      { label: "Valor", value: formatCurrency(props.processes.purchaseOrder.amount) },
    ],
  },
]);
</script>

<template>
  <div class="process-summary" data-testid="process-summary">
    <section v-for="group in groups" :key="group.title" class="process-group">
      <h3>{{ group.title }}</h3>
      <div class="process-fields">
        <div v-for="field in group.fields" :key="field.label" class="detail-field">
          <span>{{ field.label }}</span><strong>{{ field.value }}</strong>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.process-summary { display: grid; gap: 20px; }
.process-group h3 { margin: 0 0 10px; color: #2b3e58; font-size: 12px; font-weight: 800; }
.process-fields { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 16px; }
.detail-field { display: grid; align-content: start; gap: 5px; }
.detail-field > span { color: #7a879a; font-size: 10px; font-weight: 800; letter-spacing: .05em; text-transform: uppercase; }
.detail-field strong { color: #2b3e58; font-size: 13px; font-weight: 700; }
@media (max-width: 900px) { .process-fields { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 520px) { .process-fields { grid-template-columns: 1fr; } }
</style>
