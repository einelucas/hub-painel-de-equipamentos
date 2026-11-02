<script setup lang="ts">
import { reactive } from "vue";
import type { PurchaseOrder } from "~/types/equipment";
import { VBtn } from "vuetify/components";

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
    <div class="field"><VTextField v-model="form.orderNumber" label="Número da OC" maxlength="80" /></div>
    <div class="field"><VTextField v-model="form.orderedAt" label="Data da OC" type="date" /></div>
    <div class="field"><VTextField v-model="form.amount" label="Valor" type="number" min="0" step="0.01" /></div>
    <VAlert v-if="error" class="notice error" type="error" role="alert">{{ error }}</VAlert>
    <div class="form-actions">
      <VBtn variant="outlined" color="secondary" @click="emit('cancel')">Cancelar</VBtn>
      <VBtn type="submit" variant="flat" color="primary" :loading="busy" :disabled="busy">{{ busy ? "Salvando..." : "Salvar" }}</VBtn>
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
