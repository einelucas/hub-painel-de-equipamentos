<script setup lang="ts">
import type { PurchaseRequest } from "~/types/equipment";
import EquipmentPurchaseRequestRow from "~/components/equipment/purchase-requests/EquipmentPurchaseRequestRow.vue";

defineProps<{ items: PurchaseRequest[]; editable: boolean; busy: boolean }>();
const emit = defineEmits<{
  edit: [item: PurchaseRequest];
  delete: [item: PurchaseRequest];
}>();
</script>

<template>
  <div v-if="items.length === 0" class="empty-state table-empty" data-testid="purchase-requests-empty">
    <h2>Nenhuma SC/OCI cadastrada</h2>
    <p>Adicione uma solicitação para avançar a Fase 6 (exceto sob exceção de Importação).</p>
  </div>
  <div v-else class="table-wrap">
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Tipo</TableHead>
          <TableHead>Número</TableHead>
          <TableHead>Data</TableHead>
          <TableHead />
        </TableRow>
      </TableHeader>
      <TableBody>
        <EquipmentPurchaseRequestRow
          v-for="item in items"
          :key="item.id"
          :item="item"
          :editable="editable"
          :busy="busy"
          @edit="emit('edit', $event)"
          @delete="emit('delete', $event)"
        />
      </TableBody>
    </Table>
  </div>
</template>

<style scoped>
.table-wrap { padding: 0 18px 18px; overflow-x: auto; }
.table-empty { margin: auto; padding-bottom: 28px; }
</style>
