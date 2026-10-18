<script setup lang="ts">
import type { Equipment } from "~/types/equipment";
import { formatDateOnly } from "~/utils/format";
import StageBadge from "~/components/equipment/StageBadge.vue";
import WorkPackageChips from "~/components/equipment/WorkPackageChips.vue";
import DisciplineBadge from "~/components/equipment/DisciplineBadge.vue";
import CriticalityBadge from "~/components/equipment/CriticalityBadge.vue";
import { equipmentLocationLabel } from "~/utils/equipmentLocation";
import { Eye } from "lucide-vue-next";

defineProps<{ equipments: Equipment[] }>();
</script>

<template>
  <div v-if="equipments.length === 0" class="empty-state table-empty" data-testid="equipment-empty">
    <h2>Nenhum equipamento encontrado</h2>
    <p>Não há registros para os filtros selecionados. Ajuste os filtros ou cadastre o primeiro equipamento da unidade.</p>
  </div>
  <div v-else class="table-wrap">
    <Table>
      <TableHeader><TableRow><TableHead>Equipamento</TableHead><TableHead class="col-obra">Obra</TableHead><TableHead>Área</TableHead><TableHead>Disciplina</TableHead><TableHead>Work Packages</TableHead><TableHead>Responsável</TableHead><TableHead>Etapa atual</TableHead><TableHead>Startup</TableHead><TableHead>Criticidade</TableHead><TableHead class="text-center">Componentes</TableHead><TableHead /></TableRow></TableHeader>
      <TableBody>
        <TableRow v-for="equipment in equipments" :key="equipment.id">
          <TableCell class="font-semibold text-[#213758]"><NuxtLink class="name-link" :to="`/equipamentos/${equipment.id}`"><TruncatedText :text="equipment.name" /></NuxtLink></TableCell>
          <TableCell>{{ equipment.projectContext.code ?? equipment.projectContext.name }}</TableCell>
          <TableCell data-testid="equipment-location">{{ equipmentLocationLabel(equipment) ?? "—" }}</TableCell>
          <TableCell>
            <DisciplineBadge v-if="equipment.discipline" :discipline="equipment.discipline" data-testid="equipment-discipline" />
            <span v-else>—</span>
          </TableCell>
          <TableCell><WorkPackageChips :items="equipment.workPackages" /></TableCell>
          <TableCell>{{ equipment.responsibleUser?.name ?? "—" }}</TableCell>
          <TableCell><StageBadge :stage="equipment.currentStage" :name="equipment.stageName" /></TableCell>
          <TableCell>{{ formatDateOnly(equipment.startupAt) }}</TableCell>
          <TableCell><CriticalityBadge v-if="equipment.criticalityLabel || equipment.criticality" :label="equipment.criticalityLabel?.name ?? equipment.criticality!" :color="equipment.criticalityLabel?.color" /><span v-else>—</span></TableCell>
          <TableCell class="text-center font-semibold">{{ equipment.componentsCount }}</TableCell>
          <TableCell class="action-cell text-center"><NuxtLink class="detail-link" :to="`/equipamentos/${equipment.id}`" title="Ver detalhes" :aria-label="`Ver detalhes de ${equipment.name}`"><Eye :size="19" aria-hidden="true" /></NuxtLink></TableCell>
        </TableRow>
      </TableBody>
    </Table>
  </div>
</template>

<style scoped>
.table-wrap { padding: 0 18px 18px; }
.table-empty { margin: auto; }
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
/* Coluna de ações: mantém o ícone afastado da borda direita da tabela. */
.table-wrap :deep(td.action-cell) { padding-right: 28px; }
.name-link { color: #304f7e; text-decoration: none; }
.name-link:hover { text-decoration: underline; }
/* Largura mínima da coluna Obra (o valor base vale para telas largas). */
.col-obra { min-width: 150px; }
/*
 * Compactação por largura disponível.
 *
 * O conteúdo é limitado a 1680px (`.nuxt-app-main`), ou seja, a partir de
 * 1728px de viewport a tabela já tem sempre a largura máxima garantida — e é
 * esse o layout "normal" de referência. Abaixo disso (notebooks, janelas
 * menores ou escala de exibição do Windows > 100%, ex.: 1920px a 125% = 1536px
 * de viewport) as colunas ficam mais compactas para a tabela continuar cabendo
 * sem corte.
 *
 * Se ainda faltar espaço em telas muito estreitas, o `Table` rola
 * horizontalmente dentro do card (nunca corta a página).
 */
@media (max-width: 1728px) {
  .table-wrap :deep(th),
  .table-wrap :deep(td) {
    padding-inline: 10px;
  }
  .table-wrap :deep(td.action-cell) {
    padding-right: 22px;
  }
  .table-wrap :deep(.truncated-text) {
    max-width: 220px;
  }
}
@media (max-width: 1400px) {
  .table-wrap :deep(th),
  .table-wrap :deep(td) {
    padding-inline: 8px;
  }
  .table-wrap :deep(td.action-cell) {
    padding-right: 18px;
  }
  .col-obra {
    min-width: 120px;
  }
  .table-wrap :deep(.truncated-text) {
    max-width: 180px;
  }
}
</style>
