<script setup lang="ts">
import { mdiMapMarkerOutline, mdiOfficeBuildingOutline, mdiPlus, mdiDeleteOutline } from "@mdi/js";
import { VBtn } from "vuetify/components";
import type { SimulationProject, SimulationUnit } from "~/types/startupSimulation";

const props = defineProps<{
  units: SimulationUnit[];
  projects: SimulationProject[];
  unitId: string;
  projectId: string;
  loading: boolean;
  canWrite: boolean;
}>();
const emit = defineEmits<{
  "select-unit": [id: string];
  "select-project": [id: string];
  "create-unit": [];
  "create-project": [];
  "delete-unit": [];
  "delete-project": [];
}>();
const unitOptions = computed(() => props.units.map((u) => ({ id: u.id, label: u.name })));
const projectOptions = computed(() => props.projects.map((p) => ({ id: p.id, label: p.name })));
</script>

<template>
  <section class="surface simulation-scope" aria-label="Filtros exclusivos do Simulador de Startup">
    <div class="scope-heading">
      <div>
        <h2>Unidade e obra da simulação</h2>
        <p>Cadastros exclusivos desta aba, sem interferência nos filtros operacionais do Hub.</p>
      </div>
    </div>
    <div class="scope-fields">
      <div class="scope-field">
        <FloatingFilterSelect
          :model-value="unitId"
          :options="unitOptions"
          :icon="mdiOfficeBuildingOutline"
          label="Unidade do simulador"
          placeholder="Selecione uma unidade"
          :loading="loading"
          :disabled="loading"
          :clearable="false"
          density="compact"
          test-id="simulation-unit-filter"
          @change="emit('select-unit', $event)"
        />
        <VBtn
          v-if="canWrite"
          :prepend-icon="mdiPlus"
          size="small"
          color="primary"
          variant="tonal"
          :disabled="loading"
          @click="emit('create-unit')"
        >Nova unidade</VBtn>
        <VBtn
          v-if="canWrite && unitId"
          :icon="mdiDeleteOutline"
          size="small"
          variant="text"
          color="error"
          aria-label="Excluir unidade vazia do simulador"
          :disabled="loading"
          @click="emit('delete-unit')"
        />
      </div>
      <div class="scope-field">
        <FloatingFilterSelect
          :model-value="projectId"
          :options="projectOptions"
          :icon="mdiMapMarkerOutline"
          label="Obra do simulador"
          placeholder="Selecione uma obra"
          :loading="loading"
          :disabled="!unitId || loading"
          :clearable="false"
          density="compact"
          test-id="simulation-project-filter"
          @change="emit('select-project', $event)"
        />
        <VBtn
          v-if="canWrite"
          :prepend-icon="mdiPlus"
          size="small"
          color="primary"
          variant="tonal"
          :disabled="!unitId || loading"
          @click="emit('create-project')"
        >Nova obra</VBtn>
        <VBtn
          v-if="canWrite && projectId"
          :icon="mdiDeleteOutline"
          size="small"
          variant="text"
          color="error"
          aria-label="Excluir obra vazia do simulador"
          :disabled="loading"
          @click="emit('delete-project')"
        />
      </div>
    </div>
  </section>
</template>

<style scoped>
.simulation-scope { margin-bottom: 16px; padding: 16px 18px; }
.scope-heading h2 { font-size: 14px; font-weight: 800; color: #213758; margin: 0; }
.scope-heading p { font-size: 11.5px; color: #7d8a9d; margin: 4px 0 15px; }
.scope-fields { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px 18px; }
.scope-field { display: flex; align-items: flex-start; gap: 7px; min-width: 0; }
.scope-field :deep(.floating-filter-select) { flex: 1; min-width: 130px; }
.scope-field :deep(.v-btn) { margin-top: 3px; flex-shrink: 0; }
@media (max-width: 970px) { .scope-fields { grid-template-columns: minmax(0, 1fr); } }
@media (max-width: 560px) { .scope-field { flex-wrap: wrap; } }
</style>
