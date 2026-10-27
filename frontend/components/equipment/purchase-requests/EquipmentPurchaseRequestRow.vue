<script setup lang="ts">
import Button from "~/components/ui/Button.vue";
import { Pencil, Trash2 } from "lucide-vue-next";
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
