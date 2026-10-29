<script setup lang="ts">
import { mdiDownload, mdiPencilOutline, mdiTrashCanOutline } from "@mdi/js";
import { VBtn } from "vuetify/components";
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
      <VBtn
        v-if="contract.file"
        class="text-button"
        :disabled="downloadingId === contract.id"
        :loading="downloadingId === contract.id"
        variant="text"
        size="small"
        :prepend-icon="!(downloadingId === contract.id) ? mdiDownload : undefined"
       @click="emit('download', contract)">
         {{ contract.file.fileName }}
      </VBtn>
      <span v-else>—</span>
    </TableCell>
    <TableCell class="row-actions">
      <VBtn
        v-if="editable"
        class="text-button"
        variant="text"
        size="small"
        :prepend-icon="mdiPencilOutline"
       @click="emit('edit', contract)">
         Editar
      </VBtn>
      <VBtn
        v-if="editable"
        class="text-button"
        :disabled="busy"
        :loading="activeId === contract.id"
        variant="tonal" color="error"
        size="small"
        :prepend-icon="!(activeId === contract.id) ? mdiTrashCanOutline : undefined"
       @click="emit('delete', contract)">

        {{ activeId === contract.id ? "Excluindo..." : "Excluir" }}
      </VBtn>
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
