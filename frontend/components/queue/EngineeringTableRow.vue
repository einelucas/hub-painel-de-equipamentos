<script setup lang="ts">
import type { EngineeringRow } from "~/types/equipment";
import { formatDateOnly } from "~/utils/format";
import StageBadge from "~/components/equipment/StageBadge.vue";
import WorkPackageChips from "~/components/equipment/WorkPackageChips.vue";
import DisciplineBadge from "~/components/equipment/DisciplineBadge.vue";
import TipBadge from "~/components/ui/TipBadge.vue";
import { Eye } from "lucide-vue-next";

/**
 * Linha comum às duas visões da fila de Engenharia (normal/agrupada) — a
 * única diferença entre elas é a coluna "Responsável", omitida na visão
 * agrupada (o nome já vira o título do grupo, ver `EngineeringTableHeader`).
 */
defineProps<{ row: EngineeringRow; showResponsible: boolean }>();
</script>

<template>
  <TableRow>
    <TableCell class="font-semibold"><NuxtLink class="name-link" :to="`/equipamentos/${row.equipmentId}`"><TruncatedText :text="row.equipmentName" /></NuxtLink></TableCell>
    <TableCell>{{ row.unit.name }}</TableCell>
    <TableCell><StageBadge :stage="row.currentStage" :name="row.currentStageName" /></TableCell>
    <TableCell>
      <DisciplineBadge v-if="row.discipline" :discipline="row.discipline" data-testid="engineering-discipline" />
      <span v-else>—</span>
    </TableCell>
    <TableCell>
      <!-- Localização pela EAP canônica: só o código no badge (economiza
           largura), com o nome da área no balão ao passar o mouse. Cor única
           definida no `TipBadge` — a EAP não tem cor própria no catálogo,
           diferente de disciplinas e criticidades. -->
      <TipBadge
        v-if="row.eapNode"
        data-testid="eap-node-badge"
        tone="neutral"
        :label="row.eapNode.code"
        :tip="row.eapNode.name"
      />
      <span v-else>—</span>
    </TableCell>
    <TableCell><WorkPackageChips :items="row.workPackages" /></TableCell>
    <TableCell v-if="showResponsible">{{ row.responsibleUser?.name ?? "—" }}</TableCell>
    <TableCell>{{ formatDateOnly(row.startupAt) }}</TableCell>
    <TableCell><PendingBadge :pending="row.pending" :next-stage-name="row.nextStageName" /></TableCell>
    <TableCell class="action-cell">
      <NuxtLink
        class="detail-link"
        :to="`/equipamentos/${row.equipmentId}`"
        title="Ver detalhes"
        :aria-label="`Ver detalhes de ${row.equipmentName}`"
      >
        <Eye :size="19" aria-hidden="true" />
      </NuxtLink>
    </TableCell>
  </TableRow>
</template>

<style scoped>
.detail-link {
  display: inline-flex;
  align-items: center;
  color: #304f7e;
  text-decoration: none;
  transition: color .14s ease, transform .14s ease;
}
.detail-link:hover { color: #213758; transform: scale(1.14); }
.detail-link:focus-visible { border-radius: 6px; outline: 2px solid #304f7e; outline-offset: 2px; }
@media (prefers-reduced-motion: reduce) {
  .detail-link { transition: none; }
  .detail-link:hover { transform: none; }
}
.name-link { color: #304f7e; text-decoration: none; }
.name-link:hover { text-decoration: underline; }
</style>
