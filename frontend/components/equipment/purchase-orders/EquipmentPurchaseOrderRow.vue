<script setup lang="ts">
import Button from "~/components/ui/Button.vue";
import { Pencil, Trash2 } from "lucide-vue-next";
import type { PurchaseOrder } from "~/types/equipment";
import { formatCurrency, formatDateOnly } from "~/utils/format";

defineProps<{ item: PurchaseOrder; editable: boolean; busy: boolean; activeId?: string | null }>();
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
      <Button v-if="editable" class="text-button" variant="ghost" size="sm" @click="emit('edit', item)"><Pencil :size="13" /> Editar</Button>
      <Button v-if="editable" class="text-button" :disabled="busy" :loading="activeId === item.id" variant="destructive" size="sm" @click="emit('delete', item)">
        <Trash2 v-if="!(activeId === item.id)" :size="13" />
        {{ activeId === item.id ? "Excluindo..." : "Excluir" }}
      </Button>
    </TableCell>
  </TableRow>
</template>

<style scoped>
.row-actions { display: flex; gap: 12px; white-space: nowrap; }
</style>
