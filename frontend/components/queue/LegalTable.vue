<script setup lang="ts">
import type { LegalRow } from "~/types/equipment";

defineProps<{ rows: LegalRow[]; loading?: boolean }>();
</script>

<template>
  <Table :loading="loading">
    <LegalTableHeader :loading="loading" />
    <TableBody :loading="loading && rows.length === 0">
      <LegalTableRow v-for="row in rows" :key="row.equipmentId" :row="row" />
    </TableBody>
  </Table>
</template>
