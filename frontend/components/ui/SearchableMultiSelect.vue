<script setup lang="ts">
import { ElOption, ElSelect } from "element-plus";
import { computed, ref } from "vue";
import type { SearchableOption } from "~/types/ui";

/**
 * Seleção múltipla pesquisável do Hub. O `ElSelect` cuida de foco, teclado,
 * dropdown teleportado, tags nativas e acessibilidade.
 */
const props = withDefaults(
  defineProps<{
    options: SearchableOption[];
    modelValue: string[];
    label: string;
    placeholder?: string;
    disabled?: boolean;
    disabledMessage?: string;
    testId?: string;
  }>(),
  {
    placeholder: "Digite para buscar",
    disabled: false,
    disabledMessage: "Nenhuma opção disponível.",
    testId: undefined,
  },
);
const emit = defineEmits<{
  "update:modelValue": [value: string[]];
  /** Só quando a seleção de fato muda. */
  change: [value: string[]];
}>();

const root = ref<HTMLElement | null>(null);
const query = ref("");
const ordered = computed(() =>
  [...props.options].sort((left, right) =>
    left.label.localeCompare(right.label, "pt-BR", {
      numeric: true,
      sensitivity: "base",
    }),
  ),
);
const filtered = computed(() => {
  const term = query.value.trim().toLocaleLowerCase("pt-BR");
  if (!term) return ordered.value;
  return ordered.value.filter((option) =>
    [option.label, option.description, option.searchText]
      .filter(Boolean)
      .some((value) =>
        String(value).toLocaleLowerCase("pt-BR").includes(term),
      ),
  );
});
const wrapperAttrs = computed(() => ({
  "data-testid": props.testId,
  "data-selected-count": String(props.modelValue.length),
  "data-disabled": props.disabled ? "true" : "false",
  "data-placeholder": props.placeholder,
}));

function normalize(value: unknown): string[] {
  return Array.isArray(value) ? value.map(String) : [];
}

function onUpdate(value: unknown): void {
  emit("update:modelValue", normalize(value));
}

function sameSelection(left: string[], right: string[]): boolean {
  return (
    left.length === right.length &&
    left.every((value) => right.includes(value))
  );
}

function onChange(value: unknown): void {
  const next = normalize(value);
  if (sameSelection(next, props.modelValue)) return;
  emit("change", next);
}

function onFilter(value: string): void {
  query.value = value;
}

function onVisibleChange(open: boolean): void {
  // Ao fechar, a próxima abertura volta a mostrar todas as opções.
  if (!open) query.value = "";
}

</script>

<template>
  <div ref="root" class="searchable-multi-select" v-bind="wrapperAttrs">
    <ElSelect
      :model-value="props.modelValue"
      :disabled="props.disabled"
      :placeholder="props.placeholder"
      :aria-label="props.label"
      multiple
      filterable
      automatic-dropdown
      :persistent="false"
      :fit-input-width="true"
      popper-class="hub-select-popper"
      :filter-method="onFilter"
      :no-data-text="
        props.disabled
          ? props.disabledMessage
          : 'Nenhuma opção encontrada.'
      "
      class="searchable-multi-select__control"
      @update:model-value="onUpdate"
      @change="onChange"
      @visible-change="onVisibleChange"
    >
      <ElOption
        v-for="option in filtered"
        :key="option.id"
        :value="option.id"
        :label="option.label"
      >
        <span class="searchable-multi-select__option">
          <strong>{{ option.label }}</strong>
          <small v-if="option.description">{{ option.description }}</small>
        </span>
      </ElOption>
    </ElSelect>
  </div>
</template>

<style scoped>
.searchable-multi-select { min-width: 0; }
.searchable-multi-select__option { display: grid; gap: 2px; }
.searchable-multi-select__option small { color: var(--el-text-color-secondary); font-size: 12px; }
</style>
