<script setup lang="ts">
import type { EngineeringRow } from "~/types/equipment";
import { formatDate } from "~/utils/format";

definePageMeta({ middleware: "auth" });
const route = useRoute();
const auth = useAuthStore();
const queue = useQueue<EngineeringRow>("engineering");
const allowed = computed(() => auth.can("equipments:read"));

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
      @reload="queue.reload"
      @search="applySearch"
      @page="queue.goToPage"
    >
      <Table>
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
            <TableCell>{{ formatDate(row.startupAt) }}</TableCell>
            <TableCell><PendingBadge :pending="row.pending" :next-stage-name="row.nextStageName" /></TableCell>
            <TableCell><NuxtLink class="text-button" :to="`/equipamentos/${row.equipmentId}`">Ver detalhes</NuxtLink></TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </QueueShell>
  </ModuleWorkspace>
</template>

<style scoped>
.text-button { color: #304f7e; font-size: 12px; font-weight: 750; text-decoration: none; }
</style>
