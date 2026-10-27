<script setup lang="ts">
import Button from "~/components/ui/Button.vue";
import { Download, Pencil, Trash2 } from "lucide-vue-next";
import type { Contract } from "~/types/equipment";
import { formatDateOnly } from "~/utils/format";

defineProps<{
  contract: Contract;
  editable: boolean;
  busy: boolean;
  activeId?: string | null;
  downloadingId?: string | null;
}>();
const emit = defineEmits<{
  edit: [contract: Contract];
  delete: [contract: Contract];
  download: [contract: Contract];
}>();
</script>

<template>
  <TableRow :data-testid="`contract-${contract.id}`">
    <TableCell class="font-semibold">{{
      contract.contractNumber ?? "—"
    }}</TableCell>
    <TableCell>{{ formatDateOnly(contract.executedAt) }}</TableCell>
    <TableCell>
      <Button
        v-if="contract.file"
        class="text-button"
        :disabled="downloadingId === contract.id"
        :loading="downloadingId === contract.id"
        variant="ghost"
        size="sm"
        @click="emit('download', contract)"
      >
        <Download v-if="!(downloadingId === contract.id)" :size="13" /> {{ contract.file.fileName }}
      </Button>
      <span v-else>—</span>
    </TableCell>
    <TableCell class="row-actions">
      <Button
        v-if="editable"
        class="text-button"
        variant="ghost"
        size="sm"
        @click="emit('edit', contract)"
      >
        <Pencil :size="13" /> Editar
      </Button>
      <Button
        v-if="editable"
        class="text-button"
        :disabled="busy"
        :loading="activeId === contract.id"
        variant="destructive"
        size="sm"
        @click="emit('delete', contract)"
      >
        <Trash2 v-if="!(activeId === contract.id)" :size="13" />
        {{ activeId === contract.id ? "Excluindo..." : "Excluir" }}
      </Button>
    </TableCell>
  </TableRow>
</template>

<style scoped>
.row-actions {
  display: flex;
  gap: 12px;
  white-space: nowrap;
}
</style>
