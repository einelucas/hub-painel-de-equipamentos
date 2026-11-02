<script setup lang="ts">
/**
 * Cabeçalho comum às duas visões da fila de Engenharia (normal/agrupada) —
 * a única diferença entre elas é a coluna "Responsável", que só faz
 * sentido fora do agrupamento (o nome já vira o título do grupo).
 */
defineProps<{ showResponsible: boolean; loading?: boolean }>();
</script>

<template>
  <TableHeader :loading="loading">
    <TableRow>
      <TableHead>Equipamento</TableHead>
      <TableHead>Unidade</TableHead>
      <TableHead>Etapa</TableHead>
      <TableHead>Disciplina</TableHead>
      <TableHead>Área</TableHead>
      <TableHead>Pacotes</TableHead>
      <TableHead v-if="showResponsible">Responsável</TableHead>
      <TableHead>Startup</TableHead>
      <TableHead>Pendência</TableHead>
      <TableHead />
    </TableRow>
  </TableHeader>
</template>
