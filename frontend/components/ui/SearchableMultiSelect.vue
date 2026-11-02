<script setup lang="ts">
import { VAutocomplete } from "vuetify/components/VAutocomplete";
import { VChip } from "vuetify/components/VChip";
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
const menuWidth = ref<number | undefined>();

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

function removeSelection(value: unknown): void {
  onUpdate(props.modelValue.filter((item) => item !== String(value)));
}

function onMenuChange(open: boolean): void {
  if (!open) return;
  const width = root.value?.getBoundingClientRect().width;
  if (width) menuWidth.value = Math.round(width);
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
      clearable
      :no-data-text="props.disabled ? props.disabledMessage : 'Nenhuma opção encontrada.'"
      :menu-props="{
        width: menuWidth,
        minWidth: menuWidth,
        maxWidth: menuWidth,
      }"
      clear-on-select
      @update:model-value="onUpdate"
      @update:menu="onMenuChange"
    >
      <template #selection="{ item, index }">
        <VChip
          v-if="props.modelValue.length === 1 && index === 0"
          class="selection-chip"
          size="x-small"
          closable
          @click:close.stop="removeSelection(item.value)"
        >
          {{ item.title }}
        </VChip>
        <span v-else-if="props.modelValue.length > 1 && index === 0" class="selection-summary">
          {{ props.modelValue.length }} selecionados
        </span>
      </template>
    </VAutocomplete>
  </div>
</template>

<style scoped>
.searchable-multi-select { min-width: 0; }
.searchable-multi-select :deep(.v-field__input) {
  flex-wrap: nowrap;
  overflow: hidden;
}
.selection-chip {
  max-width: calc(100% - 8px);
}
.selection-chip :deep(.v-chip__content) {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.selection-summary {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  min-height: 22px;
  padding: 2px 9px;
  border: 1px solid #d7dfeb;
  border-radius: 999px;
  background: #f3f6fa;
  color: #52637a;
  font-size: 11px;
  font-weight: 650;
  white-space: nowrap;
}
</style>
