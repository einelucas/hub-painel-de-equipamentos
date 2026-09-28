<script setup lang="ts">
import type { CatalogItem, CatalogList, EngineeringRow, Responsible } from "~/types/equipment";

definePageMeta({ middleware: "auth" });
const route = useRoute();
const api = useApi();
const auth = useAuthStore();
const context = useModuleContextStore();
const queue = useQueue<EngineeringRow>("engineering");
const allowed = computed(() => auth.can("equipments:read"));

const disciplines = ref<CatalogItem[]>([]);
const responsibles = ref<Responsible[]>([]);
const disciplineId = ref("");
const responsibleUserId = ref("");
// Agrupamento é só apresentação — derivado de `responsibleUser` a cada
// carga da fila, nunca persistido (GAP-011: Ana Carolina/Uilson/etc são
// Users reais, não grupos gravados em algum catálogo).
const groupEnabled = ref(false);

async function loadFilterCatalogs(): Promise<void> {
  disciplines.value = (await api.get<CatalogList<CatalogItem>>("/disciplines")).items;
  if (context.selectedUnit) {
    responsibles.value = (
      await api.get<CatalogList<Responsible>>("/responsibles", { unit_id: context.selectedUnit })
    ).items;
  } else {
    responsibles.value = [];
  }
}

async function applyFieldFilters(): Promise<void> {
  if (disciplineId.value) queue.filters.discipline_id = disciplineId.value;
  else delete queue.filters.discipline_id;
  if (responsibleUserId.value) queue.filters.responsible_user_id = responsibleUserId.value;
  else delete queue.filters.responsible_user_id;
  await queue.reload();
}

async function reloadAll(): Promise<void> {
  await loadFilterCatalogs();
  await applyFieldFilters();
}

async function applySearch(term: string): Promise<void> {
  queue.search.value = term;
  await queue.reload();
}

onMounted(async () => {
  if (!allowed.value) {
    queue.loading.value = false;
    return;
  }
  await queue.initialize({
    unit: typeof route.query.unit === "string" ? route.query.unit : undefined,
    equipment: typeof route.query.equipment === "string" ? route.query.equipment : undefined,
  });
  await loadFilterCatalogs();
});
</script>

<template>
  <ModuleWorkspace
    eyebrow="Planejamento · Equipamentos"
    title="Fila de Engenharia"
    description="Equipamentos nas etapas técnicas iniciais, com disciplina, área e responsável."
  >
    <QueueShell
      title="Engenharia"
      description="Demandas em definição técnica e negociação."
      criteria="Critério: equipamentos nas etapas 0 a 2 (Nova demanda, Negociação e Equalização)."
      :loading="queue.loading.value"
      :refreshing="queue.refreshing.value"
      :error="queue.error.value"
      :empty="queue.items.value.length === 0"
      :pagination="queue.pagination.value"
      :page="queue.page.value"
      :allowed="allowed"
      @reload="reloadAll"
      @search="applySearch"
      @page="queue.goToPage"
    >
      <template #filters>
        <label class="field">
          <span>Disciplina</span>
          <select v-model="disciplineId" data-testid="filter-discipline" @change="applyFieldFilters">
            <option value="">Todas</option>
            <option v-for="item in disciplines" :key="item.id" :value="item.id">{{ item.name }}</option>
          </select>
        </label>
        <label class="field">
          <span>Responsável</span>
          <select
            v-model="responsibleUserId"
            :disabled="!context.selectedUnit"
            :title="!context.selectedUnit ? 'Selecione uma unidade para filtrar por responsável' : undefined"
            data-testid="filter-responsible"
            @change="applyFieldFilters"
          >
            <option value="">Todos</option>
            <option v-for="item in responsibles" :key="item.id" :value="item.id">{{ item.name }}</option>
          </select>
        </label>
        <label class="field field-check">
          <input v-model="groupEnabled" type="checkbox" data-testid="group-by-responsible">
          <span>Agrupar por responsável</span>
        </label>
      </template>

      <EngineeringTable :rows="queue.items.value" :grouped="groupEnabled" />
    </QueueShell>
  </ModuleWorkspace>
</template>

<style scoped>
.field-check { flex-direction: row; align-items: center; gap: 7px; }
.field-check input { width: 15px; height: 15px; }
</style>
