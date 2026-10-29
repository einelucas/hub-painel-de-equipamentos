<script setup lang="ts">
import { reactive } from "vue";
import type { PurchaseRequest, PurchaseRequestKind } from "~/types/equipment";
import { VBtn } from "vuetify/components";
import SearchableSelect from "~/components/ui/SearchableSelect.vue";

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

const KIND_OPTIONS = [
  { id: "SC", label: "SC" },
  { id: "OCI", label: "OCI" },
];

const form = reactive<EquipmentPurchaseRequestFormValues>({
  kind: props.item?.kind ?? "",
  requestNumber: props.item?.requestNumber ?? "",
  requestedAt: props.item?.requestedAt ?? "",
});
</script>

<template>
  <form class="item-form" @submit.prevent="emit('submit', { ...form })">
    <div class="field">
      <SearchableSelect
        :model-value="form.kind"
        :options="KIND_OPTIONS"
        :sorted="false"
        label="Tipo"
        placeholder="Buscar tipo"
        empty-label="Não informado"
        test-id="purchase-request-kind"
        @update:model-value="form.kind = $event as EquipmentPurchaseRequestFormValues['kind']"
      />
    </div>
    <label class="field"><span>Número</span><input v-model="form.requestNumber" maxlength="80"></label>
    <label class="field"><span>Data</span><input v-model="form.requestedAt" type="date"></label>
    <p v-if="error" class="notice error" role="alert">{{ error }}</p>
    <div class="form-actions">
      <VBtn type="button" variant="outlined" @click="emit('cancel')">Cancelar</VBtn>
      <VBtn type="submit" variant="tonal" :loading="busy" :disabled="busy">{{ busy ? "Salvando..." : "Salvar" }}</VBtn>
    </div>
  </form>
</template>

<style scoped>
.item-form { display: grid; gap: 14px; }
.field { display: grid; gap: 4px; font-size: 12px; }
.field span { color: #7a879a; font-size: 10px; font-weight: 800; letter-spacing: .05em; text-transform: uppercase; }
.field input:not([role="combobox"]):not([type="hidden"]) { border: 1px solid #d8dee7; border-radius: 6px; padding: 7px 9px; font-size: 13px; }
.form-actions { display: flex; justify-content: flex-end; gap: 9px; }
</style>
