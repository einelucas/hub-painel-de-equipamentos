<script setup lang="ts">
import { Pencil, Trash2 } from "lucide-vue-next";
import type { PurchaseOrder } from "~/types/equipment";
import { formatCurrency, formatDateOnly } from "~/utils/format";

defineProps<{ item: PurchaseOrder; editable: boolean; busy: boolean }>();
const emit = defineEmits<{
  edit: [item: PurchaseOrder];
  delete: [item: PurchaseOrder];
}>();
</script>

<template>
  <TableRow :data-testid="`purchase-order-${item.id}`">
    <TableCell class="font-semibold">{{ item.orderNumber ?? "—" }}</TableCell>
    <TableCell>{{ formatDateOnly(item.orderedAt) }}</TableCell>
    <TableCell>{{ formatCurrency(item.amount) }}</TableCell>
    <TableCell class="row-actions">
      <button v-if="editable" class="text-button" @click="emit('edit', item)"><Pencil :size="13" /> Editar</button>
      <button v-if="editable" class="text-button danger" :disabled="busy" @click="emit('delete', item)">
        <Trash2 :size="13" /> Excluir
      </button>
    </TableCell>
  </TableRow>
</template>

<style scoped>
.row-actions { display: flex; gap: 12px; white-space: nowrap; }
.text-button { display: inline-flex; align-items: center; gap: 5px; border: 0; padding: 4px; background: transparent; color: #304f7e; font-size: 12px; font-weight: 750; }
.text-button.danger { color: #a4453a; }
</style>
