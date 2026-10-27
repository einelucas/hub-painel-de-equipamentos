<script setup lang="ts">
import { ElPagination } from "element-plus";

/**
 * Paginação construída sobre o `ElPagination` do Element Plus
 * (`prev, pager, next` com fundo). O componente não guarda estado: recebe a
 * página atual e devolve a nova via `change` — quem carrega os dados continua
 * sendo o consumidor.
 */
const props = withDefaults(
  defineProps<{ page: number; totalPages: number; disabled?: boolean }>(),
  { disabled: false },
);
const emit = defineEmits<{ change: [page: number] }>();
</script>

<template>
  <nav class="app-pagination" aria-label="Paginação de resultados">
    <ElPagination
      :current-page="props.page"
      :page-count="props.totalPages"
      :disabled="props.disabled"
      layout="prev, pager, next"
      background
      @current-change="emit('change', $event)"
    />
  </nav>
</template>
