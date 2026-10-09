<script setup lang="ts">
import type { Equipment } from "~/types/equipment";
import { formatDateOnly } from "~/utils/format";
import StageBadge from "~/components/equipment/StageBadge.vue";
import WorkPackageChips from "~/components/equipment/WorkPackageChips.vue";
import { equipmentLocationLabel } from "~/utils/equipmentLocation";

defineProps<{ equipments: Equipment[] }>();
</script>

<template>
  <div v-if="equipments.length === 0" class="empty-state table-empty" data-testid="equipment-empty">
    <h2>Nenhum equipamento encontrado</h2>
    <p>Não há registros para os filtros selecionados. Ajuste os filtros ou cadastre o primeiro equipamento da unidade.</p>
  </div>
  <div v-else class="table-wrap">
    <Table>
      <TableHeader><TableRow><TableHead>Equipamento</TableHead><TableHead>Contexto</TableHead><TableHead>Área</TableHead><TableHead>Disciplina</TableHead><TableHead>Work Packages</TableHead><TableHead>Responsável</TableHead><TableHead>Etapa atual</TableHead><TableHead>Startup</TableHead><TableHead>Criticidade</TableHead><TableHead class="text-center">Componentes</TableHead><TableHead /></TableRow></TableHeader>
      <TableBody>
        <TableRow v-for="equipment in equipments" :key="equipment.id">
          <TableCell class="font-semibold text-[#213758]">{{ equipment.name }}</TableCell>
          <TableCell>{{ equipment.projectContext.code ?? equipment.projectContext.name }}</TableCell>
          <TableCell data-testid="equipment-location">{{ equipmentLocationLabel(equipment) ?? "—" }}</TableCell>
          <TableCell>{{ equipment.discipline?.name ?? "—" }}</TableCell>
          <TableCell><WorkPackageChips :items="equipment.workPackages" /></TableCell>
          <TableCell>{{ equipment.responsibleUser?.name ?? "—" }}</TableCell>
          <TableCell><StageBadge :stage="equipment.currentStage" :name="equipment.stageName" /></TableCell>
          <TableCell>{{ formatDateOnly(equipment.startupAt) }}</TableCell>
          <TableCell>{{ equipment.criticality ?? "—" }}</TableCell>
          <TableCell class="text-center font-semibold">{{ equipment.componentsCount }}</TableCell>
          <TableCell><NuxtLink class="detail-link" :to="`/equipamentos/${equipment.id}`">Ver detalhes</NuxtLink></TableCell>
        </TableRow>
      </TableBody>
    </Table>
  </div>
</template>

<style scoped>
.table-wrap { padding: 0 18px 18px; }
.table-empty { margin: auto; }
.detail-link { color: #304f7e; font-size: 12px; font-weight: 750; text-decoration: none; white-space: nowrap; }
.detail-link:hover { text-decoration: underline; }
</style>
