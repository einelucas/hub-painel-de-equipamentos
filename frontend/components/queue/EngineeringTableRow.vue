<script setup lang="ts">
import type { EngineeringRow } from "~/types/equipment";
import { formatDateOnly } from "~/utils/format";

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
    <TableCell>{{ row.unit.code }}</TableCell>
    <TableCell>{{ row.currentStage }} · {{ row.currentStageName }}</TableCell>
    <TableCell>{{ row.discipline?.name ?? "—" }}</TableCell>
    <TableCell>{{ row.area?.name ?? "—" }}</TableCell>
    <TableCell>{{ row.workPackages.length ? row.workPackages.map((item) => item.code ?? item.name).join(", ") : "—" }}</TableCell>
    <TableCell v-if="showResponsible">{{ row.responsibleUser?.name ?? "—" }}</TableCell>
    <TableCell>{{ formatDateOnly(row.startupAt) }}</TableCell>
    <TableCell><PendingBadge :pending="row.pending" :next-stage-name="row.nextStageName" /></TableCell>
    <TableCell><NuxtLink class="text-button" :to="`/equipamentos/${row.equipmentId}`">Ver detalhes</NuxtLink></TableCell>
  </TableRow>
</template>

<style scoped>
.text-button { color: #304f7e; font-size: 12px; font-weight: 750; text-decoration: none; }
</style>
