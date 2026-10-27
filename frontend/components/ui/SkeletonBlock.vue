<script setup lang="ts">
import { ElSkeleton } from "element-plus";

/**
 * Placeholder de carregamento construído sobre o `ElSkeleton` do Element Plus.
 * `lines` renderiza barras de texto (última mais curta); `rows` renderiza
 * blocos maiores, no recorte das linhas de tabela do Hub.
 */
const props = withDefaults(defineProps<{ lines?: number; rows?: number }>(), {
  lines: 0,
  rows: 0,
});
</script>

<template>
  <div class="skeleton-block" aria-hidden="true">
    <ElSkeleton
      v-if="props.lines > 0"
      animated
      :rows="props.lines"
      class="skeleton-block--lines"
    />
    <ElSkeleton
      v-if="props.rows > 0"
      animated
      :rows="props.rows"
      class="skeleton-block--rows"
    />
  </div>
</template>

<style scoped>
.skeleton-block--rows :deep(.el-skeleton__item) {
  height: 38px;
  margin-top: 6px;
}
</style>
