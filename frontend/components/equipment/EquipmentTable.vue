<script setup lang="ts">
import type { Equipment } from "~/types/equipment";
import { formatDateOnly } from "~/utils/format";
import { stageTone } from "~/utils/stages";

defineProps<{ equipments: Equipment[] }>();
</script>

<template>
  <div v-if="equipments.length === 0" class="empty-state table-empty" data-testid="equipment-empty">
    <h2>Nenhum equipamento encontrado</h2>
    <p>Não há registros para os filtros selecionados. Ajuste os filtros ou cadastre o primeiro equipamento da unidade.</p>
  </div>
  <div v-else class="table-wrap">
    <Table>
      <TableHeader><TableRow><TableHead>Equipamento</TableHead><TableHead>Contexto</TableHead><TableHead>Área</TableHead><TableHead>Disciplina</TableHead><TableHead>Pacotes de trabalho</TableHead><TableHead>Responsável</TableHead><TableHead>Etapa atual</TableHead><TableHead>Startup</TableHead><TableHead>Criticidade</TableHead><TableHead class="text-center">Componentes</TableHead><TableHead /></TableRow></TableHeader>
      <TableBody>
        <TableRow v-for="equipment in equipments" :key="equipment.id">
          <TableCell class="font-semibold text-[#213758]">{{ equipment.name }}</TableCell>
          <TableCell>{{ equipment.projectContext.code ?? equipment.projectContext.name }}</TableCell>
          <TableCell>{{ equipment.area?.name ?? "—" }}</TableCell>
          <TableCell>{{ equipment.discipline?.name ?? "—" }}</TableCell>
          <TableCell>
            <span v-if="equipment.workPackages.length === 0">—</span>
            <div v-else class="wp-chips">
              <span v-for="item in equipment.workPackages.slice(0, 3)" :key="item.id" class="wp-chip">{{ item.code ?? item.name }}</span>
              <span v-if="equipment.workPackages.length > 3" class="wp-chip wp-chip--more">+{{ equipment.workPackages.length - 3 }}</span>
            </div>
          </TableCell>
          <TableCell>{{ equipment.responsibleUser?.name ?? "—" }}</TableCell>
          <TableCell><span class="stage-badge" :class="stageTone(equipment.currentStage)">{{ equipment.currentStage }} · {{ equipment.stageName }}</span></TableCell>
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
.stage-badge { display: inline-flex; white-space: nowrap; border-radius: 999px; padding: 4px 8px; font-size: 11px; font-weight: 750; }
.stage-badge--new { background: #eef2f7; color: #53647a; }
.stage-badge--progress { background: #fff3df; color: #9b6418; }
.stage-badge--advanced { background: #e8f1fc; color: #2f5f9c; }
.stage-badge--complete { background: #eaf4e5; color: #477a32; }
.detail-link { color: #304f7e; font-size: 12px; font-weight: 750; text-decoration: none; white-space: nowrap; }
.detail-link:hover { text-decoration: underline; }
/* Compacto: no máx. 3 chips + "+N", nunca aumenta a altura da linha. */
.wp-chips { display: flex; flex-wrap: wrap; gap: 4px; max-width: 220px; }
.wp-chip { display: inline-flex; white-space: nowrap; border-radius: 999px; padding: 3px 8px; font-size: 10.5px; font-weight: 700; background: #eef2f7; color: #2b3e58; }
.wp-chip--more { background: #e1e7ef; color: #56657c; }
</style>
