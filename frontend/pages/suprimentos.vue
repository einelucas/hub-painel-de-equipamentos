<script setup lang="ts">
import { SlidersHorizontal } from "lucide-vue-next";
import type { ProcurementRow } from "~/types/equipment";
import { formatCurrency, formatDateOnly } from "~/utils/format";

definePageMeta({ middleware: "auth" });
const route = useRoute();
const auth = useAuthStore();
const queue = useQueue<ProcurementRow>("procurement");
const allowed = computed(() => auth.can("equipments:read"));
const canAdminister = computed(() => auth.can("suppliers:write"));
const showAdmin = ref(false);

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
    title="Fila de Suprimentos"
    description="Solicitações SC/OCI e ordens de compra em aprovação."
  >
    <QueueShell
      title="Suprimentos"
      description="Processos entre a solicitação SC/OCI e a aprovação da ordem de compra."
      criteria="Critério: equipamentos nas etapas 6 e 7 (SC ou OCI e Aprovação da OC)."
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
      <template #actions>
        <button
          v-if="canAdminister"
          class="btn"
          data-testid="admin-button"
          @click="showAdmin = true"
        >
          <SlidersHorizontal :size="16" /> Administração
        </button>
      </template>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Equipamento</TableHead>
            <TableHead>Unidade</TableHead>
            <TableHead>Responsável</TableHead>
            <TableHead>Etapa</TableHead>
            <TableHead>Tipo</TableHead>
            <TableHead>Número SC/OCI</TableHead>
            <TableHead>Data SC/OCI</TableHead>
            <TableHead>Número OC</TableHead>
            <TableHead>Data OC</TableHead>
            <TableHead>Valor OC</TableHead>
            <TableHead>Fornecedor principal</TableHead>
            <TableHead>Pendência</TableHead>
            <TableHead />
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow v-for="row in queue.items.value" :key="row.equipmentId">
            <TableCell class="font-semibold">{{ row.equipmentName }}</TableCell>
            <TableCell>{{ row.unit.code }}</TableCell>
            <TableCell>{{ row.responsibleUser?.name ?? "—" }}</TableCell>
            <TableCell>{{ row.currentStage }} · {{ row.currentStageName }}</TableCell>
            <TableCell>{{ row.kind ?? "—" }}</TableCell>
            <TableCell>{{ row.requestNumber ?? "—" }}</TableCell>
            <TableCell>{{ formatDateOnly(row.requestedAt) }}</TableCell>
            <TableCell>{{ row.orderNumber ?? "—" }}</TableCell>
            <TableCell>{{ formatDateOnly(row.orderedAt) }}</TableCell>
            <TableCell>{{ formatCurrency(row.amount) }}</TableCell>
            <TableCell>{{ row.primarySupplier?.legalName ?? "—" }}</TableCell>
            <TableCell><PendingBadge :pending="row.pending" :next-stage-name="row.nextStageName" /></TableCell>
            <TableCell><NuxtLink class="text-button" :to="`/equipamentos/${row.equipmentId}`">Ver detalhes</NuxtLink></TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </QueueShell>

    <SupplierAdmin
      v-if="canAdminister"
      :open="showAdmin"
      @close="showAdmin = false"
      @changed="queue.load"
    />
  </ModuleWorkspace>
</template>

<style scoped>
.text-button { color: #304f7e; font-size: 12px; font-weight: 750; text-decoration: none; }
</style>
