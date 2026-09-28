<script setup lang="ts">
import { reactive } from "vue";
import type { PurchaseRequest, PurchaseRequestKind } from "~/types/equipment";

export interface EquipmentPurchaseRequestFormValues {
  kind: "" | PurchaseRequestKind;
  requestNumber: string;
  requestedAt: string;
}

/** `item` nulo = criação. O modal só monta o formulário quando aberto,
 * então os campos partem sempre do item recebido. */
const props = defineProps<{
  item: PurchaseRequest | null;
  busy: boolean;
  error: string;
}>();
const emit = defineEmits<{
  submit: [values: EquipmentPurchaseRequestFormValues];
  cancel: [];
}>();

const form = reactive<EquipmentPurchaseRequestFormValues>({
  kind: props.item?.kind ?? "",
  requestNumber: props.item?.requestNumber ?? "",
  requestedAt: props.item?.requestedAt ?? "",
});
</script>

<template>
  <form class="item-form" @submit.prevent="emit('submit', { ...form })">
    <label class="field">
      <span>Tipo</span>
      <select v-model="form.kind">
        <option value="">Não informado</option>
        <option value="SC">SC</option>
        <option value="OCI">OCI</option>
      </select>
    </label>
    <label class="field"><span>Número</span><input v-model="form.requestNumber" maxlength="80"></label>
    <label class="field"><span>Data</span><input v-model="form.requestedAt" type="date"></label>
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
.field input, .field select { border: 1px solid #d8dee7; border-radius: 6px; padding: 7px 9px; font-size: 13px; }
.form-actions { display: flex; justify-content: flex-end; gap: 9px; }
</style>
