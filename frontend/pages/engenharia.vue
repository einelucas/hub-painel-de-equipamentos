<script setup lang="ts">
import type { CatalogItem, CatalogList, EngineeringRow, Responsible } from "~/types/equipment";
import { groupByResponsible } from "~/utils/engineering";
import { formatDateOnly } from "~/utils/format";

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

const groupedRows = computed(() => groupByResponsible(queue.items.value));

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

      <Table v-if="!groupEnabled">
        <TableHeader>
          <TableRow>
            <TableHead>Equipamento</TableHead>
            <TableHead>Unidade</TableHead>
            <TableHead>Etapa</TableHead>
            <TableHead>Disciplina</TableHead>
            <TableHead>Área</TableHead>
            <TableHead>Pacotes</TableHead>
            <TableHead>Responsável</TableHead>
            <TableHead>Startup</TableHead>
            <TableHead>Pendência</TableHead>
            <TableHead />
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow v-for="row in queue.items.value" :key="row.equipmentId">
            <TableCell class="font-semibold">{{ row.equipmentName }}</TableCell>
            <TableCell>{{ row.unit.code }}</TableCell>
            <TableCell>{{ row.currentStage }} · {{ row.currentStageName }}</TableCell>
            <TableCell>{{ row.discipline?.name ?? "—" }}</TableCell>
            <TableCell>{{ row.area?.name ?? "—" }}</TableCell>
            <TableCell>{{ row.workPackages.length ? row.workPackages.map((item) => item.code ?? item.name).join(", ") : "—" }}</TableCell>
            <TableCell>{{ row.responsibleUser?.name ?? "—" }}</TableCell>
            <TableCell>{{ formatDateOnly(row.startupAt) }}</TableCell>
            <TableCell><PendingBadge :pending="row.pending" :next-stage-name="row.nextStageName" /></TableCell>
            <TableCell><NuxtLink class="text-button" :to="`/equipamentos/${row.equipmentId}`">Ver detalhes</NuxtLink></TableCell>
          </TableRow>
        </TableBody>
      </Table>

      <div v-else class="grouped" data-testid="engineering-grouped">
        <section v-for="group in groupedRows" :key="group.key" class="group-block">
          <h3 class="group-title">{{ group.label }} <span class="group-count">({{ group.rows.length }})</span></h3>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Equipamento</TableHead>
                <TableHead>Unidade</TableHead>
                <TableHead>Etapa</TableHead>
                <TableHead>Disciplina</TableHead>
                <TableHead>Área</TableHead>
                <TableHead>Pacotes</TableHead>
                <TableHead>Startup</TableHead>
                <TableHead>Pendência</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow v-for="row in group.rows" :key="row.equipmentId">
                <TableCell class="font-semibold">{{ row.equipmentName }}</TableCell>
                <TableCell>{{ row.unit.code }}</TableCell>
                <TableCell>{{ row.currentStage }} · {{ row.currentStageName }}</TableCell>
                <TableCell>{{ row.discipline?.name ?? "—" }}</TableCell>
                <TableCell>{{ row.area?.name ?? "—" }}</TableCell>
                <TableCell>{{ row.workPackages.length ? row.workPackages.map((item) => item.code ?? item.name).join(", ") : "—" }}</TableCell>
                <TableCell>{{ formatDateOnly(row.startupAt) }}</TableCell>
                <TableCell><PendingBadge :pending="row.pending" :next-stage-name="row.nextStageName" /></TableCell>
                <TableCell><NuxtLink class="text-button" :to="`/equipamentos/${row.equipmentId}`">Ver detalhes</NuxtLink></TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </section>
      </div>
    </QueueShell>
  </ModuleWorkspace>
</template>

<style scoped>
.text-button { color: #304f7e; font-size: 12px; font-weight: 750; text-decoration: none; }
.field-check { flex-direction: row; align-items: center; gap: 7px; }
.field-check input { width: 15px; height: 15px; }
.grouped { display: grid; gap: 22px; }
.group-title { margin: 0 0 8px; color: #2b3e58; font-size: 13px; font-weight: 800; }
.group-count { color: #8b96a5; font-weight: 700; }
</style>
