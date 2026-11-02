<script setup lang="ts">
import { reactive, ref } from "vue";
import { VBtn } from "vuetify/components";
import type { EquipmentComponent } from "~/types/equipment";

const props = defineProps<{ equipmentId: string; component?: EquipmentComponent | null }>();
const emit = defineEmits<{ saved: [component: EquipmentComponent]; cancel: [] }>();
const api = useApi();
const saving = ref(false);
const error = ref("");
const form = reactive({
  name: props.component?.name ?? "",
  tag: props.component?.tag ?? "",
  // Startup próprio do subitem — independente de `equipment.startupAt`, e
  // nunca herdado dele (GAP-009).
  startupAt: props.component?.startupAt ?? "",
  sector: props.component?.sector ?? "",
  leadTimeDays: props.component?.leadTimeDays?.toString() ?? "",
  preStartDays: props.component?.preStartDays?.toString() ?? "",
  contractDeliveryAt: props.component?.contractDeliveryAt ?? "",
  freightDays: props.component?.freightDays?.toString() ?? "",
});

function optionalNumber(value: string): number | null {
  return value === "" ? null : Number(value);
}

async function submit(): Promise<void> {
  if (saving.value) return;
  if (!form.name.trim()) {
    error.value = "Informe o nome do componente.";
    return;
  }
  saving.value = true;
  error.value = "";
  const payload = {
    name: form.name.trim(),
    tag: form.tag || null,
    startupAt: form.startupAt || null,
    sector: form.sector || null,
    leadTimeDays: optionalNumber(form.leadTimeDays),
    preStartDays: optionalNumber(form.preStartDays),
    contractDeliveryAt: form.contractDeliveryAt || null,
    freightDays: optionalNumber(form.freightDays),
  };
  try {
    const result = props.component
      ? await api.patch<EquipmentComponent>(`/components/${props.component.id}`, payload)
      : await api.post<EquipmentComponent>(`/equipments/${props.equipmentId}/components`, payload);
    emit("saved", result);
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "Não foi possível salvar o componente.";
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <form class="equipment-form" @submit.prevent="submit">
    <VAlert v-if="error" type="error" role="alert">{{ error }}</VAlert>
    <div class="form-grid">
      <div class="field field-wide"><VTextField v-model="form.name" label="Componente *" required maxlength="500" /></div>
      <div class="field"><VTextField v-model="form.tag" label="Tag" maxlength="100" /></div>
      <div class="field"><VTextField v-model="form.startupAt" label="Startup" type="date" /></div>
      <div class="field"><VTextField v-model="form.sector" label="Setor" maxlength="120" /></div>
      <div class="field"><VTextField v-model="form.leadTimeDays" label="Lead time (dias)" type="number" min="0" /></div>
      <div class="field"><VTextField v-model="form.preStartDays" label="Pré-start (dias)" type="number" min="0" /></div>
      <div class="field"><VTextField v-model="form.contractDeliveryAt" label="Entrega contratual" type="date" /></div>
      <div class="field"><VTextField v-model="form.freightDays" label="Frete (dias)" type="number" min="0" /></div>
    </div>
    <div class="form-actions"><VBtn variant="outlined" color="secondary" @click="emit('cancel')">Cancelar</VBtn><VBtn type="submit" variant="flat" color="primary" :loading="saving" :disabled="saving">{{ saving ? "Salvando..." : "Salvar componente" }}</VBtn></div>
  </form>
</template>

<style scoped>
.equipment-form { display: grid; gap: 18px; }
.form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
.field-wide { grid-column: 1 / -1; }
.form-actions { display: flex; justify-content: flex-end; gap: 9px; }
@media (max-width: 620px) { .form-grid { grid-template-columns: 1fr; } .field-wide { grid-column: auto; } }
</style>
