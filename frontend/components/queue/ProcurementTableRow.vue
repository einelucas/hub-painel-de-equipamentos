<script setup lang="ts">
import type { ProcurementRow } from "~/types/equipment";
import { formatCurrency, formatDateOnly } from "~/utils/format";
import StageBadge from "~/components/equipment/StageBadge.vue";

defineProps<{ row: ProcurementRow }>();
</script>

<template>
  <TableRow>
    <TableCell class="font-semibold">{{ row.equipmentName }}</TableCell>
    <TableCell>{{ row.unit.name }}</TableCell>
    <TableCell>{{ row.responsibleUser?.name ?? "—" }}</TableCell>
    <TableCell><StageBadge :stage="row.currentStage" :name="row.currentStageName" /></TableCell>
    <TableCell>{{ row.kind ?? "—" }}</TableCell>
    <TableCell>{{ row.requestNumber ?? "—" }}</TableCell>
    <TableCell>{{ formatDateOnly(row.requestedAt) }}</TableCell>
    <TableCell>{{ row.orderNumber ?? "—" }}</TableCell>
    <TableCell>{{ formatDateOnly(row.orderedAt) }}</TableCell>
    <TableCell>{{ formatCurrency(row.amount) }}</TableCell>
    <TableCell>{{ row.primarySupplier?.legalName ?? "—" }}</TableCell>
    <TableCell><PendingBadge :pending="row.pending" :next-stage-name="row.nextStageName" /></TableCell>
    <TableCell><NuxtLink class="text-button" :to="`/equipamentos/${row.equipmentId}`">Ver detalhes</NuxtLink></TableCell>
  </TableRow>
</template>

<style scoped>
.text-button { color: #304f7e; font-size: 12px; font-weight: 750; text-decoration: none; }
</style>
