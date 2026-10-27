<script setup lang="ts">
import { ElCheckbox } from "element-plus";

/**
 * Checkbox construído sobre o `ElCheckbox` do Element Plus.
 * O componente é sempre usado dentro do `label.area-option` do painel de
 * áreas; o `margin-right` padrão do EP é zerado para respeitar o layout.
 */
const model = defineModel<boolean>({ default: false });
</script>

<template>
  <ElCheckbox v-model="model" class="hub-checkbox" />
</template>

<style scoped>
.hub-checkbox {
  height: auto;
  margin-right: 0;
}
</style>
