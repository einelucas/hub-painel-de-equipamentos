<script setup lang="ts">
import type { LegalRow } from "~/types/equipment";

definePageMeta({ middleware: "auth" });
const route = useRoute();
const auth = useAuthStore();
const queue = useQueue<LegalRow>("legal");
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
      <LegalTable :rows="queue.items.value" />
    </QueueShell>
  </ModuleWorkspace>
</template>
