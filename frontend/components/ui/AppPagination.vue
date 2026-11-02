<script setup lang="ts">
import { computed } from "vue";
import { VPagination } from "vuetify/components";

/**
 * Paginação controlada sobre o `VPagination`. O contrato do Hub continua
 * 1-based e sem estado próprio: o consumidor permanece responsável pela API.
 */
const props = withDefaults(
  defineProps<{ page: number; totalPages: number; disabled?: boolean }>(),
  { disabled: false },
);
const emit = defineEmits<{ change: [page: number] }>();

const pageCount = computed(() => Math.max(0, Math.floor(props.totalPages)));
const currentPage = computed(() => {
  if (pageCount.value === 0) return 1;
  return Math.min(Math.max(1, Math.floor(props.page)), pageCount.value);
});

function changePage(page: number): void {
  if (
    props.disabled
    || !Number.isInteger(page)
    || page < 1
    || page > pageCount.value
    || page === props.page
  ) return;
  emit("change", page);
}
</script>

<template>
  <VPagination
    v-if="pageCount > 0"
    class="app-pagination"
    :model-value="currentPage"
    :length="pageCount"
    :disabled="props.disabled"
    color="primary"
    active-color="primary"
    density="comfortable"
    size="small"
    rounded="lg"
    aria-label="Paginação de resultados"
    previous-aria-label="Página anterior"
    next-aria-label="Próxima página"
    page-aria-label="Ir para a página {0}"
    current-page-aria-label="Página atual, página {0}"
    @update:model-value="changePage"
  />
  <nav
    v-else
    class="app-pagination"
    aria-label="Paginação de resultados"
  />
</template>
