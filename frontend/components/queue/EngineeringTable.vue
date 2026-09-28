<script setup lang="ts">
import { computed } from "vue";
import type { EngineeringRow } from "~/types/equipment";
import { groupByResponsible } from "~/utils/engineering";

/**
 * Tabela da fila de Engenharia — normal ou agrupada por responsável
 * (GAP-011, só apresentação: `groupByResponsible` deriva os grupos a cada
 * render a partir de `row.responsibleUser`, nunca grava nada). A página
 * continua responsável por carregar a fila, os catálogos e os filtros;
 * aqui chegam só as linhas já filtradas e o modo de exibição.
 */
const props = defineProps<{ rows: EngineeringRow[]; grouped: boolean }>();

const groups = computed(() => groupByResponsible(props.rows));
</script>

<template>
  <Table v-if="!grouped">
    <EngineeringTableHeader :show-responsible="true" />
    <TableBody>
      <EngineeringTableRow v-for="row in rows" :key="row.equipmentId" :row="row" :show-responsible="true" />
    </TableBody>
  </Table>

  <div v-else class="grouped" data-testid="engineering-grouped">
    <section v-for="group in groups" :key="group.key" class="group-block">
      <h3 class="group-title">{{ group.label }} <span class="group-count">({{ group.rows.length }})</span></h3>
      <Table>
        <EngineeringTableHeader :show-responsible="false" />
        <TableBody>
          <EngineeringTableRow v-for="row in group.rows" :key="row.equipmentId" :row="row" :show-responsible="false" />
        </TableBody>
      </Table>
    </section>
  </div>
</template>

<style scoped>
.grouped { display: grid; gap: 22px; }
.group-title { margin: 0 0 8px; color: #2b3e58; font-size: 13px; font-weight: 800; }
.group-count { color: #8b96a5; font-weight: 700; }
</style>
