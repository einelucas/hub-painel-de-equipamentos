<script setup lang="ts">
import type { EquipmentComponent } from "~/types/equipment";

const props = defineProps<{ equipmentId: string; component?: EquipmentComponent | null }>();
const emit = defineEmits<{ saved: [component: EquipmentComponent]; cancel: [] }>();
const api = useApi();
const saving = ref(false);
const error = ref("");
const form = reactive({
  name: props.component?.name ?? "",
  tag: props.component?.tag ?? "",
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
  if (!form.name.trim()) {
    error.value = "Informe o nome do componente.";
    return;
  }
  saving.value = true;
  error.value = "";
  const payload = {
    name: form.name.trim(),
    tag: form.tag || null,
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
    <p v-if="error" class="notice error" role="alert">{{ error }}</p>
    <div class="form-grid">
      <label class="field field-wide"><span>Componente *</span><input v-model="form.name" required maxlength="200"></label>
      <label class="field"><span>Tag</span><input v-model="form.tag" maxlength="100"></label>
      <label class="field"><span>Setor</span><input v-model="form.sector" maxlength="120"></label>
      <label class="field"><span>Lead time (dias)</span><input v-model="form.leadTimeDays" type="number" min="0"></label>
      <label class="field"><span>Pré-start (dias)</span><input v-model="form.preStartDays" type="number" min="0"></label>
      <label class="field"><span>Entrega contratual</span><input v-model="form.contractDeliveryAt" type="date"></label>
      <label class="field"><span>Frete (dias)</span><input v-model="form.freightDays" type="number" min="0"></label>
    </div>
    <div class="form-actions"><button type="button" class="btn" @click="emit('cancel')">Cancelar</button><button class="btn primary" type="submit" :disabled="saving">{{ saving ? "Salvando..." : "Salvar componente" }}</button></div>
  </form>
</template>

<style scoped>
.equipment-form { display: grid; gap: 18px; }
.form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
.field-wide { grid-column: 1 / -1; }
.form-actions { display: flex; justify-content: flex-end; gap: 9px; }
@media (max-width: 620px) { .form-grid { grid-template-columns: 1fr; } .field-wide { grid-column: auto; } }
</style>
