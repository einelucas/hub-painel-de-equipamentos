<script setup lang="ts">
import FloatingFilterSelect from "~/components/ui/FloatingFilterSelect.vue";
import { mdiTag, mdiAccount } from "@mdi/js";
import type {
  CatalogItem,
  CatalogList,
  EngineeringRow,
  Responsible,
} from "~/types/equipment";
import type { SearchableOption } from "~/types/ui";
import { toOptions } from "~/utils/selectOptions";

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
// carga da fila, nunca persistido (GAP-011: Analista Sintético A/Analista Sintético D/etc são
// Users reais, não grupos gravados em algum catálogo).
const groupEnabled = ref(false);
const disciplineOptions = computed(() => toOptions(disciplines.value));
const responsibleOptions = computed<SearchableOption[]>(() =>
  responsibles.value.map((item) => ({
    id: item.id,
    label: item.name,
    searchText: item.email,
  })),
);

const catalogsLoading = ref(false);

async function loadFilterCatalogs(): Promise<void> {
  catalogsLoading.value = true;
  try {
    await fetchFilterCatalogs();
  } finally {
    catalogsLoading.value = false;
  }
}

async function fetchFilterCatalogs(): Promise<void> {
  disciplines.value = (
    await api.get<CatalogList<CatalogItem>>("/disciplines")
  ).items;
  if (context.selectedUnit) {
    responsibles.value = (
      await api.get<CatalogList<Responsible>>("/responsibles", {
        unit_id: context.selectedUnit,
      })
    ).items;
  } else {
    responsibles.value = [];
  }
}

async function applyFieldFilters(): Promise<void> {
  if (disciplineId.value) queue.filters.discipline_id = disciplineId.value;
  else delete queue.filters.discipline_id;
  if (responsibleUserId.value)
    queue.filters.responsible_user_id = responsibleUserId.value;
  else delete queue.filters.responsible_user_id;
  await queue.reload();
}

async function reloadAll(): Promise<void> {
  await loadFilterCatalogs();
  await applyFieldFilters();
}

onMounted(async () => {
  if (!allowed.value) {
    queue.loading.value = false;
    return;
  }
  await queue.initialize({
    unit: typeof route.query.unit === "string" ? route.query.unit : undefined,
    project:
      typeof route.query.project === "string" ? route.query.project : undefined,
    equipment:
      typeof route.query.equipment === "string"
        ? route.query.equipment
        : undefined,
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
      :show-search="false"
      @reload="reloadAll"
      @refresh="queue.load"
      @page="queue.goToPage"
    >
      <template #filters>
        <div class="field">
          <FloatingFilterSelect
            v-model="disciplineId"
            :options="disciplineOptions"
            :disabled="catalogsLoading"
            :icon="mdiTag"
            label="Disciplina"
            placeholder="Buscar disciplina"
            empty-label="Todas"
            test-id="filter-discipline"
            @change="applyFieldFilters"
          />
        </div>
        <div class="field">
          <FloatingFilterSelect
            v-model="responsibleUserId"
            :options="responsibleOptions"
            :disabled="!context.selectedUnit || catalogsLoading"
            :title="
              !context.selectedUnit
                ? 'Selecione uma unidade para filtrar por responsável'
                : undefined
            "
            :icon="mdiAccount"
            label="Responsável"
            placeholder="Buscar responsável"
            empty-label="Todos"
            test-id="filter-responsible"
            @change="applyFieldFilters"
          />
        </div>
        <label
          class="field-inline group-toggle"
          :class="{ active: groupEnabled }"
        >
          <input
            v-model="groupEnabled"
            type="checkbox"
            data-testid="group-by-responsible"
          />
          <span>Agrupar por responsável</span>
        </label>
      </template>

      <EngineeringTable :rows="queue.items.value" :grouped="groupEnabled" />
    </QueueShell>
  </ModuleWorkspace>
</template>

<style scoped>
.group-toggle {
  margin-top: 5px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  height: 41px;
  padding: 0 12px;
  border: 1px solid #d8e0ea;
  border-radius: 9px;
  background: #fff;
  color: #26364d;
  font-size: 13px;
  white-space: nowrap;
  cursor: pointer;
  transition:
    border-color 0.17s ease,
    background-color 0.17s ease;
}
.group-toggle.active {
  border-color: #6687b8;
  background: #f2f6fc;
}
.group-toggle input {
  width: 15px;
  height: 15px;
  margin: 0;
  cursor: pointer;
}
</style>
