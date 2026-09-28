<script setup lang="ts">
import type { LegalRow } from "~/types/equipment";
import { formatDateOnly } from "~/utils/format";
import StageBadge from "~/components/equipment/StageBadge.vue";

defineProps<{ row: LegalRow }>();

function flag(value: boolean): string {
  return value ? "Sim" : "Não";
}
</script>

<template>
  <TableRow>
    <TableCell class="font-semibold">{{ row.equipmentName }}</TableCell>
    <TableCell>{{ row.unit.code }}</TableCell>
    <TableCell>{{ row.responsibleUser?.name ?? "—" }}</TableCell>
    <TableCell><StageBadge :stage="row.currentStage" :name="row.currentStageName" /></TableCell>
    <TableCell>{{ row.ticketNumber ?? "—" }}</TableCell>
    <TableCell>{{ formatDateOnly(row.openedAt) }}</TableCell>
    <TableCell>{{ flag(row.draftPrepared) }}</TableCell>
    <TableCell>{{ flag(row.draftApproved) }}</TableCell>
    <TableCell>{{ row.contractNumber ?? "—" }}</TableCell>
    <TableCell>{{ formatDateOnly(row.executedAt) }}</TableCell>
    <TableCell>{{ formatDateOnly(row.deliveryAt) }}</TableCell>
    <TableCell><PendingBadge :pending="row.pending" :next-stage-name="row.nextStageName" /></TableCell>
    <TableCell><NuxtLink class="text-button" :to="`/equipamentos/${row.equipmentId}`">Ver detalhes</NuxtLink></TableCell>
  </TableRow>
</template>

<style scoped>
.text-button { color: #304f7e; font-size: 12px; font-weight: 750; text-decoration: none; }
</style>
