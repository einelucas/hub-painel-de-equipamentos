<script setup lang="ts">
import type { PurchaseOrder } from "~/types/equipment";
import EquipmentPurchaseOrderRow from "~/components/equipment/purchase-orders/EquipmentPurchaseOrderRow.vue";

defineProps<{ items: PurchaseOrder[]; editable: boolean; busy: boolean }>();
const emit = defineEmits<{
  edit: [item: PurchaseOrder];
  delete: [item: PurchaseOrder];
}>();
</script>

<template>
  <div v-if="items.length === 0" class="empty-state table-empty" data-testid="purchase-orders-empty">
    <h2>Nenhuma OC cadastrada</h2>
    <p>É necessária ao menos uma OC para concluir o processo (Fase 7 → 8).</p>
  </div>
  <div v-else class="table-wrap">
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Número</TableHead>
          <TableHead>Data</TableHead>
          <TableHead>Valor</TableHead>
          <TableHead />
        </TableRow>
      </TableHeader>
      <TableBody>
        <EquipmentPurchaseOrderRow
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
