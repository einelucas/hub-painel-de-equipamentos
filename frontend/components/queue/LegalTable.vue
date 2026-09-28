<script setup lang="ts">
import type { LegalRow } from "~/types/equipment";

defineProps<{ rows: LegalRow[] }>();
</script>

<template>
  <Table>
    <LegalTableHeader />
    <TableBody>
      <LegalTableRow v-for="row in rows" :key="row.equipmentId" :row="row" />
    </TableBody>
  </Table>
</template>
