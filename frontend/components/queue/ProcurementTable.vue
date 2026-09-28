<script setup lang="ts">
import type { ProcurementRow } from "~/types/equipment";

defineProps<{ rows: ProcurementRow[] }>();
</script>

<template>
  <Table>
    <ProcurementTableHeader />
    <TableBody>
      <ProcurementTableRow v-for="row in rows" :key="row.equipmentId" :row="row" />
    </TableBody>
  </Table>
</template>
