<script setup lang="ts">
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
      <button
        v-if="contract.file"
        class="text-button"
        :disabled="downloadingId === contract.id"
        :aria-busy="downloadingId === contract.id"
        @click="emit('download', contract)"
      >
        <span
          v-if="downloadingId === contract.id"
          class="spinner-small"
          aria-hidden="true"
        />
        <Download v-else :size="13" /> {{ contract.file.fileName }}
      </button>
      <span v-else>—</span>
    </TableCell>
    <TableCell class="row-actions">
      <button
        v-if="editable"
        class="text-button"
        @click="emit('edit', contract)"
      >
        <Pencil :size="13" /> Editar
      </button>
      <button
        v-if="editable"
        class="text-button danger"
        :disabled="busy"
        :aria-busy="activeId === contract.id"
        @click="emit('delete', contract)"
      >
        <span
          v-if="activeId === contract.id"
          class="spinner-small"
          aria-hidden="true"
        />
        <Trash2 v-else :size="13" />
        {{ activeId === contract.id ? "Excluindo..." : "Excluir" }}
      </button>
    </TableCell>
  </TableRow>
</template>

<style scoped>
.row-actions {
  display: flex;
  gap: 12px;
  white-space: nowrap;
}
.text-button {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  border: 0;
  padding: 4px;
  background: transparent;
  color: #304f7e;
  font-size: 12px;
  font-weight: 750;
}
.text-button.danger {
  color: #a4453a;
}
</style>
