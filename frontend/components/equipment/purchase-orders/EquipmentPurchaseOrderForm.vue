<script setup lang="ts">
import { reactive } from "vue";
import type { PurchaseOrder } from "~/types/equipment";

export interface EquipmentPurchaseOrderFormValues {
  orderNumber: string;
  orderedAt: string;
  /** v-model em input type="number" entrega número ao digitar e "" quando vazio. */
  amount: string | number;
}

/** `item` nulo = criação. O modal só monta o formulário quando aberto,
 * então os campos partem sempre do item recebido. */
const props = defineProps<{
  item: PurchaseOrder | null;
  busy: boolean;
  error: string;
}>();
const emit = defineEmits<{
  submit: [values: EquipmentPurchaseOrderFormValues];
  cancel: [];
}>();

const form = reactive<EquipmentPurchaseOrderFormValues>({
  orderNumber: props.item?.orderNumber ?? "",
  orderedAt: props.item?.orderedAt ?? "",
  amount: props.item && props.item.amount !== null ? String(props.item.amount) : "",
});
</script>

<template>
  <form class="item-form" @submit.prevent="emit('submit', { ...form })">
    <label class="field"><span>Número da OC</span><input v-model="form.orderNumber" maxlength="80"></label>
    <label class="field"><span>Data da OC</span><input v-model="form.orderedAt" type="date"></label>
    <label class="field"><span>Valor</span><input v-model="form.amount" type="number" min="0" step="0.01"></label>
    <p v-if="error" class="notice error" role="alert">{{ error }}</p>
    <div class="form-actions">
      <button type="button" class="btn" @click="emit('cancel')">Cancelar</button>
      <button type="submit" class="btn primary" :disabled="busy">{{ busy ? "Salvando..." : "Salvar" }}</button>
    </div>
  </form>
</template>

<style scoped>
.item-form { display: grid; gap: 14px; }
.field { display: grid; gap: 4px; font-size: 12px; }
.field span { color: #7a879a; font-size: 10px; font-weight: 800; letter-spacing: .05em; text-transform: uppercase; }
.field input { border: 1px solid #d8dee7; border-radius: 6px; padding: 7px 9px; font-size: 13px; }
.form-actions { display: flex; justify-content: flex-end; gap: 9px; }
</style>
