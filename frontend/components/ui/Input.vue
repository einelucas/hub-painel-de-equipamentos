<script setup lang="ts">
const props = defineProps<{ type?: string; label?: string }>();
const model = defineModel<string | number>();
</script>

<template>
  <VTextField
    :type="props.type ?? 'text'"
    :label="props.label"
    :model-value="model ?? ''"
    @update:model-value="model = $event ?? ''"
  />
</template>
