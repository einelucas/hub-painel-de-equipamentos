<script setup lang="ts">
import { SlidersHorizontal } from "lucide-vue-next";
import type { ProcurementRow } from "~/types/equipment";
import Button from "~/components/ui/Button.vue";

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
    project: typeof route.query.project === "string" ? route.query.project : undefined,
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
        <Button
          v-if="canAdminister"
          variant="outline"
          data-testid="admin-button"
          @click="showAdmin = true"
        >
          <SlidersHorizontal :size="16" /> Administração
        </Button>
      </template>

      <ProcurementTable :rows="queue.items.value" />
    </QueueShell>

    <SupplierAdmin
      v-if="canAdminister"
      :open="showAdmin"
      @close="showAdmin = false"
      @changed="queue.load"
    />
  </ModuleWorkspace>
</template>
