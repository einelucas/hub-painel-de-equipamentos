<script setup lang="ts">
import { computed } from "vue";
import type { Component } from "vue";

const props = withDefaults(defineProps<{
  modelValue: string;
  label: string;
  placeholder?: string;
  icon?: Component;
  disabled?: boolean;
  clearable?: boolean;
  testId?: string;
}>(), {
  placeholder: "Digite para buscar",
  icon: undefined,
  disabled: false,
  clearable: true,
  testId: undefined,
});

const emit = defineEmits<{
  "update:modelValue": [value: string];
  focus: [event: FocusEvent];
  blur: [event: FocusEvent];
  clear: [];
}>();

const hasValue = computed(() => Boolean(props.modelValue));

function update(value: unknown): void {
  emit("update:modelValue", String(value ?? ""));
}

function clear(): void {
  emit("update:modelValue", "");
  emit("clear");
}
</script>

<template>
  <VTextField
    :model-value="props.modelValue"
    :label="props.label"
    :placeholder="props.placeholder"
    :disabled="props.disabled"
    :clearable="props.clearable"
    :data-testid="props.testId"
    :data-filled="hasValue ? 'true' : 'false'"
    class="floating-filter-input"
    type="text"
    @update:model-value="update"
    @focus="emit('focus', $event)"
    @blur="emit('blur', $event)"
    @click:clear="clear"
  >
    <template v-if="props.icon" #prepend-inner>
      <component :is="props.icon" :size="16" :stroke-width="1.9" />
    </template>
  </VTextField>
</template>

<style scoped>
.floating-filter-input { width: 100%; min-width: 0; }
</style>
