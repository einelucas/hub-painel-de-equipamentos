<script setup lang="ts">
import type { CatalogItem, CatalogList, Equipment } from "~/types/equipment";

const props = defineProps<{ unitId: string; equipment?: Equipment | null }>();
const emit = defineEmits<{ saved: [equipment: Equipment]; cancel: [] }>();
const api = useApi();
const contexts = ref<CatalogItem[]>([]);
const areas = ref<CatalogItem[]>([]);
const disciplines = ref<CatalogItem[]>([]);
const workPackages = ref<CatalogItem[]>([]);
const loading = ref(true);
const saving = ref(false);
const error = ref("");
const form = reactive({
  name: props.equipment?.name ?? "",
  projectContextId: props.equipment?.projectContext.id ?? "",
  origin: props.equipment?.origin ?? "",
  startupAt: props.equipment?.startupAt ?? "",
  disciplineId: props.equipment?.discipline?.id ?? "",
  areaId: props.equipment?.area?.id ?? "",
  workPackageId: props.equipment?.workPackage?.id ?? "",
  criticality: props.equipment?.criticality ?? "",
  capexEstimated: props.equipment?.capexEstimated?.toString() ?? "",
});

async function loadWorkPackages(): Promise<void> {
  workPackages.value = [];
  if (!form.projectContextId) return;
  workPackages.value = (
    await api.get<CatalogList<CatalogItem>>("/work-packages", {
      project_context_id: form.projectContextId,
    })
  ).items;
  if (!workPackages.value.some((item) => item.id === form.workPackageId)) form.workPackageId = "";
}

async function loadCatalogs(): Promise<void> {
  loading.value = true;
  try {
    const [contextResult, areaResult, disciplineResult] = await Promise.all([
      api.get<CatalogList<CatalogItem>>(`/units/${props.unitId}/project-contexts`),
      api.get<CatalogList<CatalogItem>>("/areas", { unit_id: props.unitId }),
      api.get<CatalogList<CatalogItem>>("/disciplines"),
    ]);
    contexts.value = contextResult.items;
    areas.value = areaResult.items;
    disciplines.value = disciplineResult.items;
    if (!form.projectContextId && contexts.value.length === 1) form.projectContextId = contexts.value[0]!.id;
    await loadWorkPackages();
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "Não foi possível carregar os catálogos.";
  } finally {
    loading.value = false;
  }
}

async function submit(): Promise<void> {
  if (!form.name.trim() || !form.projectContextId) {
    error.value = "Informe o nome e o contexto do equipamento.";
    return;
  }
  saving.value = true;
  error.value = "";
  const payload: Record<string, unknown> = {
    name: form.name.trim(),
    projectContextId: form.projectContextId,
    origin: form.origin || null,
    startupAt: form.startupAt || null,
    disciplineId: form.disciplineId || null,
    areaId: form.areaId || null,
    workPackageId: form.workPackageId || null,
    criticality: form.criticality || null,
    capexEstimated: form.capexEstimated === "" ? null : Number(form.capexEstimated),
  };
  try {
    const result = props.equipment
      ? await api.patch<Equipment>(`/equipments/${props.equipment.id}`, payload)
      : await api.post<Equipment>("/equipments", payload);
    emit("saved", result);
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "Não foi possível salvar o equipamento.";
  } finally {
    saving.value = false;
  }
}

onMounted(loadCatalogs);
</script>

<template>
  <div v-if="loading" class="form-loading"><span class="spinner" /> Carregando catálogos...</div>
  <form v-else class="equipment-form" @submit.prevent="submit">
    <p v-if="error" class="notice error" role="alert">{{ error }}</p>
    <div class="form-grid">
      <label class="field field-wide">
        <span>Equipamento *</span>
        <input v-model="form.name" maxlength="200" required>
      </label>
      <label class="field">
        <span>Contexto *</span>
        <select v-model="form.projectContextId" required @change="loadWorkPackages">
          <option value="">Selecione</option>
          <option v-for="item in contexts" :key="item.id" :value="item.id">{{ item.code }} · {{ item.name }}</option>
        </select>
      </label>
      <label class="field"><span>Origem</span><input v-model="form.origin" maxlength="160"></label>
      <label class="field"><span>Área</span><select v-model="form.areaId"><option value="">Não informada</option><option v-for="item in areas" :key="item.id" :value="item.id">{{ item.name }}</option></select></label>
      <label class="field"><span>Disciplina</span><select v-model="form.disciplineId"><option value="">Não informada</option><option v-for="item in disciplines" :key="item.id" :value="item.id">{{ item.name }}</option></select></label>
      <label class="field"><span>Pacote de trabalho</span><select v-model="form.workPackageId"><option value="">Não informado</option><option v-for="item in workPackages" :key="item.id" :value="item.id">{{ item.code }} · {{ item.name }}</option></select></label>
      <label class="field"><span>Startup</span><input v-model="form.startupAt" type="date"></label>
      <label class="field"><span>Criticidade</span><input v-model="form.criticality" maxlength="40" placeholder="Conforme classificação oficial"></label>
      <label class="field"><span>CAPEX estimado</span><input v-model="form.capexEstimated" type="number" min="0" step="0.01"></label>
      <p v-if="equipment" class="stage-note field-wide">A etapa atual é alterada pelo fluxo do processo, na aba Processo.</p>
    </div>
    <div class="form-actions">
      <button type="button" class="btn" @click="emit('cancel')">Cancelar</button>
      <button type="submit" class="btn primary" :disabled="saving">{{ saving ? "Salvando..." : "Salvar equipamento" }}</button>
    </div>
  </form>
</template>

<style scoped>
.form-loading { display: flex; min-height: 180px; align-items: center; justify-content: center; gap: 12px; color: #68778c; }
.equipment-form { display: grid; gap: 18px; }
.form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
.field-wide { grid-column: 1 / -1; }
.stage-note { margin: 0; color: #8b96a5; font-size: 11px; }
.form-actions { display: flex; justify-content: flex-end; gap: 9px; padding-top: 4px; }
@media (max-width: 620px) { .form-grid { grid-template-columns: 1fr; } .field-wide { grid-column: auto; } }
</style>
