<script setup lang="ts" generic="T extends string | string[] | null = string">
import { VAutocomplete } from "vuetify/components/VAutocomplete";
import { computed, ref } from "vue";
import type { Component } from "vue";
import type { SearchableOption } from "~/types/ui";
import { toAutocompleteItems, AUTOCOMPLETE_FILTER_KEYS } from "~/utils/autocomplete";

const props = withDefaults(
  defineProps<{
    modelValue: T;
    label: string;
    options: SearchableOption[];
    icon?: Component;
    placeholder?: string;
    disabled?: boolean;
    loading?: boolean;
    clearable?: boolean;
    filterable?: boolean;
    multiple?: boolean;
    emptyLabel?: string;
    emptyValue?: string;
    sorted?: boolean;
    testId?: string;
    noDataText?: string;
    disabledText?: string;
  }>(),
  {
    icon: undefined,
    placeholder: "Digite para buscar",
    disabled: false,
    loading: false,
    clearable: true,
    filterable: true,
    multiple: false,
    emptyLabel: "",
    emptyValue: "",
    sorted: true,
    testId: undefined,
    noDataText: "Nenhuma opção encontrada.",
    disabledText: "Nenhuma opção disponível.",
  },
);

const emit = defineEmits<{
  "update:modelValue": [value: T];
  change: [value: T];
  focus: [event: FocusEvent];
  blur: [event: FocusEvent];
  "visible-change": [open: boolean];
}>();

const root = ref<HTMLElement | null>(null);

const selectedLabel = computed(() => {
  const values = props.multiple
    ? Array.isArray(props.modelValue)
      ? props.modelValue
      : []
    : props.modelValue === null || props.modelValue === undefined
      ? []
      : [String(props.modelValue)];
  return props.options
    .filter((option) => values.includes(option.id))
    .map((option) => option.label)
    .join(", ");
});

const items = computed(() =>
  toAutocompleteItems(props.options, {
    emptyLabel: props.emptyLabel || undefined,
    emptyValue: props.emptyValue,
    sorted: props.sorted,
  }),
);

function normalize(value: unknown): T {
  if (props.multiple) {
    return (Array.isArray(value) ? value.map(String) : []) as T;
  }
  if (value === undefined || value === null || value === "") {
    return props.emptyValue as T;
  }
  return String(value) as T;
}

function sameValue(left: T, right: T): boolean {
  if (Array.isArray(left) && Array.isArray(right)) {
    return left.length === right.length && left.every((item) => right.includes(item));
  }
  return left === right;
}

function onUpdate(value: unknown): void {
  const next = normalize(value);
  emit("update:modelValue", next);
  if (!sameValue(next, props.modelValue)) emit("change", next);
}

function onMenuChange(open: boolean): void {
  emit("visible-change", open);
}
</script>

<template>
  <div ref="root" class="floating-filter-select" :data-testid="testId" :data-selected-label="selectedLabel" :data-disabled="props.disabled ? 'true' : 'false'">
    <VAutocomplete
      :model-value="props.modelValue"
      :items="items"
      item-title="title"
      item-value="value"
      :filter-keys="props.filterable ? [...AUTOCOMPLETE_FILTER_KEYS] : []"
      :ignore-accents="true"
      :no-filter="!props.filterable"
      :label="props.label"
      :placeholder="props.placeholder"
      :disabled="props.disabled"
      :loading="props.loading"
      :clearable="props.clearable"
      :multiple="props.multiple"
      :chips="props.multiple"
      :closable-chips="props.multiple"
      variant="outlined"
      color="primary"
      density="comfortable"
      hide-details="auto"
      :no-data-text="props.disabled ? props.disabledText : props.noDataText"
      @update:model-value="onUpdate"
      @update:menu="onMenuChange"
    >
      <template v-if="props.icon" #prepend-inner>
        <component :is="props.icon" :size="16" :stroke-width="1.9" />
      </template>
    </VAutocomplete>
  </div>
</template>

<style scoped>
.floating-filter-select { min-width: 0; }
</style>