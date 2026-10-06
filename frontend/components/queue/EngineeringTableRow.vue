<script setup lang="ts">
import type { EngineeringRow } from "~/types/equipment";
import { formatDateOnly } from "~/utils/format";
import StageBadge from "~/components/equipment/StageBadge.vue";
import WorkPackageChips from "~/components/equipment/WorkPackageChips.vue";

/**
 * Linha comum às duas visões da fila de Engenharia (normal/agrupada) — a
 * única diferença entre elas é a coluna "Responsável", omitida na visão
 * agrupada (o nome já vira o título do grupo, ver `EngineeringTableHeader`).
 */
defineProps<{ row: EngineeringRow; showResponsible: boolean }>();
</script>

<template>
  <TableRow>
    <TableCell class="font-semibold">{{ row.equipmentName }}</TableCell>
    <TableCell>{{ row.unit.name }}</TableCell>
    <TableCell><StageBadge :stage="row.currentStage" :name="row.currentStageName" /></TableCell>
    <TableCell>{{ row.discipline?.name ?? "—" }}</TableCell>
    <TableCell>{{ row.area?.name ?? "—" }}</TableCell>
    <TableCell><WorkPackageChips :items="row.workPackages" /></TableCell>
    <TableCell v-if="showResponsible">{{ row.responsibleUser?.name ?? "—" }}</TableCell>
    <TableCell>{{ formatDateOnly(row.startupAt) }}</TableCell>
    <TableCell><PendingBadge :pending="row.pending" :next-stage-name="row.nextStageName" /></TableCell>
    <TableCell><NuxtLink class="text-button" :to="`/equipamentos/${row.equipmentId}`">Ver detalhes</NuxtLink></TableCell>
  </TableRow>
</template>

<style scoped>
.text-button { color: #304f7e; font-size: 12px; font-weight: 750; text-decoration: none; white-space: nowrap; }
</style>
