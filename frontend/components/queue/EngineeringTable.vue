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

/**
 * Larguras fixas (em px) das colunas. Cada grupo é uma `<table>` própria: sem
 * larguras explícitas o navegador calcula a largura pelo conteúdo de cada
 * grupo e as tabelas ficam desalinhadas entre si. Com `table-layout: fixed` +
 * `<colgroup>` idêntico, todas as tabelas (e a visão normal) compartilham a
 * mesma grade. A coluna "Responsável" só existe fora do agrupamento.
 */
const COLUMN_WIDTHS = {
  equipment: 300,
  unit: 130,
  stage: 150,
  discipline: 120,
  area: 80,
  packages: 140,
  responsible: 160,
  startup: 110,
  pending: 300,
  actions: 120,
} as const;

const columns = computed(() => {
  const { responsible, ...shared } = COLUMN_WIDTHS;
  const widths = props.grouped
    ? [shared.equipment, shared.unit, shared.stage, shared.discipline, shared.area, shared.packages, shared.startup, shared.pending, shared.actions]
    : [shared.equipment, shared.unit, shared.stage, shared.discipline, shared.area, shared.packages, responsible, shared.startup, shared.pending, shared.actions];
  return widths;
});

const minWidth = computed(() => `${columns.value.reduce((total, width) => total + width, 0)}px`);
</script>

<template>
  <Table v-if="!grouped" class="table-fixed" :style="{ minWidth }">
    <colgroup>
      <col v-for="(width, index) in columns" :key="index" :style="{ width: `${width}px` }">
    </colgroup>
    <EngineeringTableHeader :show-responsible="true" />
    <TableBody>
      <EngineeringTableRow v-for="row in rows" :key="row.equipmentId" :row="row" :show-responsible="true" />
    </TableBody>
  </Table>

  <div v-else class="grouped" data-testid="engineering-grouped">
    <section v-for="group in groups" :key="group.key" class="group-block">
      <h3 class="group-title">{{ group.label }} <span class="group-count">({{ group.rows.length }})</span></h3>
      <Table class="table-fixed" :style="{ minWidth }">
        <colgroup>
          <col v-for="(width, index) in columns" :key="index" :style="{ width: `${width}px` }">
        </colgroup>
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
