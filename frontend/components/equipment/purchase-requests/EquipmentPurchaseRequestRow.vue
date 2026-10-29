<script setup lang="ts">
import { mdiPencilOutline, mdiTrashCanOutline } from "@mdi/js";
import { VBtn } from "vuetify/components";
import type { PurchaseRequest } from "~/types/equipment";
import { formatDateOnly } from "~/utils/format";

defineProps<{ item: PurchaseRequest; editable: boolean; busy: boolean; activeId?: string | null }>();
const emit = defineEmits<{
  edit: [item: PurchaseRequest];
  delete: [item: PurchaseRequest];
}>();
</script>

<template>
  <TableRow :data-testid="`purchase-request-${item.id}`">
    <TableCell class="font-semibold">{{ item.kind ?? "—" }}</TableCell>
    <TableCell>{{ item.requestNumber ?? "—" }}</TableCell>
    <TableCell>{{ formatDateOnly(item.requestedAt) }}</TableCell>
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
