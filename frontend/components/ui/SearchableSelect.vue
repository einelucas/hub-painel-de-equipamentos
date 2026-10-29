<script setup lang="ts">
import { VAutocomplete } from "vuetify/components/VAutocomplete";
import { computed, nextTick, onMounted, ref, watch } from "vue";
import type { SearchableOption } from "~/types/ui";
import { toAutocompleteItems, AUTOCOMPLETE_FILTER_KEYS } from "~/utils/autocomplete";

/**
 * Select pesquisável do Hub baseado no `VAutocomplete` nativo do Vuetify.
 */
const props = withDefaults(
  defineProps<{
    options: SearchableOption[];
    modelValue: string;
    label: string;
    /** Ícone MDI opcional, renderizado pelo próprio Vuetify. */
    icon?: string;
    placeholder?: string;
    emptyLabel?: string;
    emptyValue?: string;
    disabled?: boolean;
    testId?: string;
    sorted?: boolean;
    clearable?: boolean;
    required?: boolean;
  }>(),
  {
    icon: undefined,
    placeholder: "Digite para buscar",
    emptyLabel: "Não informado",
    emptyValue: "",
    disabled: false,
    testId: undefined,
    sorted: true,
    clearable: true,
    required: false,
  },
);
const emit = defineEmits<{
  "update:modelValue": [value: string];
  change: [value: string];
}>();

const root = ref<HTMLElement | null>(null);

const items = computed(() =>
  toAutocompleteItems(props.options, {
    emptyLabel: props.clearable ? props.emptyLabel : undefined,
    emptyValue: props.emptyValue,
    sorted: props.sorted,
  }),
);

const isEmpty = computed(() => props.modelValue === props.emptyValue);

const wrapperAttrs = computed(() => ({
  "data-selected-label": props.options.find((item) => item.id === props.modelValue)?.label ?? "",
  "data-disabled": props.disabled ? "true" : "false",
  "data-required": props.required ? "true" : "false",
  "data-placeholder": isEmpty.value ? props.emptyLabel : props.placeholder,
  "data-testid": props.testId,
}));

function normalize(value: unknown): string {
  if (value === undefined || value === null) return props.emptyValue;
  return String(value);
}

function onUpdate(value: unknown): void {
  const next = normalize(value);
  const changed = next !== props.modelValue;
  emit("update:modelValue", next);
  if (changed) emit("change", next);
}

function selectInput(): HTMLInputElement | null {
  return root.value?.querySelector<HTMLInputElement>("input[role='combobox']") ?? null;
}

function syncAria(): void {
  const input = selectInput();
  if (!input) return;
  if (props.required) input.setAttribute("aria-required", "true");
  else input.removeAttribute("aria-required");
  if (props.testId) input.setAttribute("data-testid", props.testId);
  else input.removeAttribute("data-testid");
}

function onInvalid(event: Event): void {
  event.preventDefault();
  const input = selectInput();
  input?.setAttribute("aria-invalid", "true");
  input?.focus();
}

onMounted(() => {
  void nextTick(syncAria);
});
watch(
  () => [props.required, props.disabled, props.testId, props.modelValue] as const,
  () => {
    void nextTick(syncAria);
  },
);
</script>

<template>
  <div ref="root" class="searchable-select" v-bind="wrapperAttrs">
    <input
      v-if="props.required"
      class="searchable-select__required"
      type="text"
      tabindex="-1"
      aria-hidden="true"
      :required="true"
      :disabled="props.disabled"
      :value="isEmpty ? '' : props.modelValue"
      @invalid="onInvalid"
    >
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
      :clearable="props.clearable"
      no-data-text="Nenhuma opção encontrada."
      @update:model-value="onUpdate"
    />
  </div>
</template>

<style scoped>
.searchable-select { position: relative; min-width: 0; }
.searchable-select__required {
  position: absolute; width: 1px; height: 1px; margin: -1px; padding: 0;
  overflow: hidden; border: 0; opacity: 0; pointer-events: none;
}
</style>