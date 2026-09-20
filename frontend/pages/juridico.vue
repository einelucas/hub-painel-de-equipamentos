<script setup lang="ts">
import type { LegalRow } from "~/types/equipment";
import { formatDate } from "~/utils/format";

definePageMeta({ middleware: "auth" });
const route = useRoute();
const auth = useAuthStore();
const queue = useQueue<LegalRow>("legal");
const allowed = computed(() => auth.can("equipments:read"));

function flag(value: boolean): string {
  return value ? "Sim" : "Não";
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
});
</script>

<template>
  <ModuleWorkspace
    eyebrow="Planejamento · Equipamentos"
    title="Fila Jurídica"
    description="Chamados, minutas e contratos em andamento."
  >
    <QueueShell
      title="Jurídico"
      description="Processos entre a abertura do chamado e a escrituração do contrato."
      criteria="Critério: equipamentos nas etapas 3 a 5 (Abertura do chamado, Aprovação da minuta e Escrituração do contrato)."
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
            <TableHead>Chamado</TableHead>
            <TableHead>Abertura</TableHead>
            <TableHead>Minuta elaborada</TableHead>
            <TableHead>Minuta aprovada</TableHead>
            <TableHead>Contrato</TableHead>
            <TableHead>Escrituração</TableHead>
            <TableHead>Pendência</TableHead>
            <TableHead />
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow v-for="row in queue.items.value" :key="row.equipmentId">
            <TableCell class="font-semibold">{{ row.equipmentName }}</TableCell>
            <TableCell>{{ row.unit.code }}</TableCell>
            <TableCell>{{ row.currentStage }} · {{ row.currentStageName }}</TableCell>
            <TableCell>{{ row.ticketNumber ?? "—" }}</TableCell>
            <TableCell>{{ formatDate(row.openedAt) }}</TableCell>
            <TableCell>{{ flag(row.draftPrepared) }}</TableCell>
            <TableCell>{{ flag(row.draftApproved) }}</TableCell>
            <TableCell>{{ row.contractNumber ?? "—" }}</TableCell>
            <TableCell>{{ formatDate(row.executedAt) }}</TableCell>
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
