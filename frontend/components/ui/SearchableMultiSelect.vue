<script setup lang="ts">
import { VAutocomplete } from "vuetify/components/VAutocomplete";
import { computed, ref } from "vue";
import type { SearchableOption } from "~/types/ui";
import { toAutocompleteItems, AUTOCOMPLETE_FILTER_KEYS } from "~/utils/autocomplete";

const props = withDefaults(
  defineProps<{
    options: SearchableOption[];
    modelValue: string[];
    label: string;
    /** Ícone MDI opcional, renderizado pelo próprio Vuetify. */
    icon?: string;
    placeholder?: string;
    disabled?: boolean;
    disabledMessage?: string;
    testId?: string;
  }>(),
  {
    icon: undefined,
    placeholder: "Digite para buscar",
    disabled: false,
    disabledMessage: "Nenhuma opção disponível.",
    testId: undefined,
  },
);
const emit = defineEmits<{
  "update:modelValue": [value: string[]];
  change: [value: string[]];
}>();

const root = ref<HTMLElement | null>(null);

const items = computed(() =>
  toAutocompleteItems(props.options, { sorted: true }),
);

const wrapperAttrs = computed(() => ({
  "data-testid": props.testId,
  "data-selected-count": String(props.modelValue.length),
  "data-disabled": props.disabled ? "true" : "false",
  "data-placeholder": props.placeholder,
}));

function normalize(value: unknown): string[] {
  return Array.isArray(value) ? value.map(String) : [];
}

function sameSelection(left: string[], right: string[]): boolean {
  return left.length === right.length && left.every((value) => right.includes(value));
}

function onUpdate(value: unknown): void {
  const next = normalize(value);
  const changed = !sameSelection(next, props.modelValue);
  emit("update:modelValue", next);
  if (changed) emit("change", next);
}

</script>

<template>
  <div ref="root" class="searchable-multi-select" v-bind="wrapperAttrs">
    <VAutocomplete
      :model-value="props.modelValue"
      :items="items"
      item-title="title"
      item-value="value"
      :filter-keys="[...AUTOCOMPLETE_FILTER_KEYS]"
      :ignore-accents="true"
      :label="props.label"
      :prepend-inner-icon="props.icon"
      :disabled="props.disabled"
      multiple
      chips
      closable-chips
      clearable
      variant="outlined"
      color="primary"
      density="comfortable"
      hide-details="auto"
      :no-data-text="props.disabled ? props.disabledMessage : 'Nenhuma opção encontrada.'"
      clear-on-select
      @update:model-value="onUpdate"
    />
  </div>
</template>

<style scoped>
.searchable-multi-select { min-width: 0; }
</style>