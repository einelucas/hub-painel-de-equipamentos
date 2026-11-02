<script setup lang="ts">
import type { ProcurementRow } from "~/types/equipment";

defineProps<{ rows: ProcurementRow[]; loading?: boolean }>();
</script>

<template>
  <Table :loading="loading">
    <ProcurementTableHeader :loading="loading" />
    <TableBody :loading="loading && rows.length === 0">
      <ProcurementTableRow v-for="row in rows" :key="row.equipmentId" :row="row" />
    </TableBody>
  </Table>
</template>
