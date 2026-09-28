<script setup lang="ts">
import type { Contract } from "~/types/equipment";
import EquipmentContractRow from "~/components/equipment/contracts/EquipmentContractRow.vue";

defineProps<{ contracts: Contract[]; editable: boolean; busy: boolean }>();
const emit = defineEmits<{
  edit: [contract: Contract];
  delete: [contract: Contract];
  download: [contract: Contract];
}>();
</script>

<template>
  <div
    v-if="contracts.length === 0"
    class="empty-state table-empty"
    data-testid="contracts-empty"
  >
    <h2>Nenhum contrato cadastrado</h2>
    <p>Adicione um contrato para escriturar o processo (Fase 5).</p>
  </div>
  <div v-else class="table-wrap">
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Número</TableHead>
          <TableHead>Escrituração</TableHead>
          <TableHead>Arquivo</TableHead>
          <TableHead />
        </TableRow>
      </TableHeader>
      <TableBody>
        <EquipmentContractRow
          v-for="item in contracts"
          :key="item.id"
          :contract="item"
          :editable="editable"
          :busy="busy"
          @edit="emit('edit', $event)"
          @delete="emit('delete', $event)"
          @download="emit('download', $event)"
        />
      </TableBody>
    </Table>
  </div>
</template>

<style scoped>
.table-wrap {
  padding: 0 18px 18px;
  overflow-x: auto;
}
.table-empty {
  margin: auto;
  padding-bottom: 28px;
}
</style>
