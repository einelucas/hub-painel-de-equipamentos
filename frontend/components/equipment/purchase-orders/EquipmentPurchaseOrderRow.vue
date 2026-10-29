<script setup lang="ts">
import { mdiPencilOutline, mdiTrashCanOutline } from "@mdi/js";
import { VBtn } from "vuetify/components";
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
      <VBtn v-if="editable" class="text-button" variant="text" size="small" :prepend-icon="mdiPencilOutline" @click="emit('edit', item)"> Editar</VBtn>
      <VBtn v-if="editable" class="text-button" :disabled="busy" :loading="activeId === item.id" variant="tonal" color="error" size="small" :prepend-icon="!(activeId === item.id) ? mdiTrashCanOutline : undefined" @click="emit('delete', item)">

        {{ activeId === item.id ? "Excluindo..." : "Excluir" }}
      </VBtn>
    </TableCell>
  </TableRow>
</template>

<style scoped>
.row-actions { display: flex; gap: 12px; white-space: nowrap; }
</style>
