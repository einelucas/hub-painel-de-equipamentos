<script setup lang="ts">
import { ElOption, ElSelect } from "element-plus";
import { computed, nextTick, ref } from "vue";
import type { SearchableOption } from "~/types/ui";

/**
 * Seleção múltipla pesquisável do Hub. O `ElSelect` cuida de foco, teclado,
 * dropdown teleportado e acessibilidade; os chips mantêm o visual anterior e
 * continuam removíveis pelo teclado.
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
const selected = computed(() =>
  ordered.value.filter((item) => props.modelValue.includes(item.id)),
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

function inputElement(): HTMLInputElement | null {
  return root.value?.querySelector<HTMLInputElement>(".el-select__input") ?? null;
}

/** Remove pelo chip e devolve o foco ao campo, sem abrir/fechar o menu. */
function removeOption(id: string, event: MouseEvent): void {
  event.stopPropagation();
  const next = props.modelValue.filter((item) => item !== id);
  emit("update:modelValue", next);
  emit("change", next);
  void nextTick(() => inputElement()?.focus());
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
      <template #tag="{ selectDisabled }">
        <span
          v-for="option in selected"
          :key="option.id"
          class="searchable-multi-select__chip"
          :title="option.description || undefined"
        >
          {{ option.label }}
          <button
            v-if="!selectDisabled"
            type="button"
            :aria-label="`Remover ${option.label}`"
            @click="removeOption(option.id, $event)"
          >
            <span aria-hidden="true">×</span>
          </button>
        </span>
      </template>
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
.searchable-multi-select {
  position: relative;
  min-width: 0;
}

.searchable-multi-select :deep(.el-select__wrapper) {
  min-height: 39px;
  align-items: flex-start;
  border-radius: 9px;
  padding: 7px 9px;
  background: #fff;
  box-shadow: 0 0 0 1px #d8e1ec inset;
  font-size: 12px;
}

.searchable-multi-select :deep(.el-select__wrapper.is-focused) {
  box-shadow:
    0 0 0 1px #5277aa inset,
    0 0 0 2px rgb(82 119 170 / 12%);
}

.searchable-multi-select :deep(.el-select__wrapper.is-disabled) {
  background: #f6f7f9;
  box-shadow: 0 0 0 1px #dfe5ed inset;
}

.searchable-multi-select :deep(.el-select__selection) {
  flex-wrap: wrap;
  gap: 5px;
}

.searchable-multi-select :deep(.el-select__selected-item) {
  color: #263d5d;
}

.searchable-multi-select :deep(.el-select__input) {
  color: #263d5d;
  font-size: 12px;
}

.searchable-multi-select :deep(.el-select__placeholder) {
  color: #718096;
}

.searchable-multi-select__chip {
  display: inline-flex;
  max-width: 100%;
  align-items: center;
  gap: 4px;
  border-radius: 6px;
  padding: 4px 5px 4px 8px;
  background: #eef4fb;
  color: #315889;
  font-size: 10.5px;
  font-weight: 750;
  line-height: 1.4;
}

.searchable-multi-select__chip button {
  display: grid;
  width: 16px;
  height: 16px;
  border: 0;
  border-radius: 4px;
  padding: 0;
  background: transparent;
  color: inherit;
  font-size: 14px;
  line-height: 1;
  cursor: pointer;
  place-items: center;
}

.searchable-multi-select__chip button:hover,
.searchable-multi-select__chip button:focus-visible {
  background: rgb(49 88 137 / 14%);
}

.searchable-multi-select__chip button:focus-visible {
  outline: 2px solid #304f7e;
  outline-offset: 1px;
}

.searchable-multi-select__option {
  display: grid;
  min-width: 0;
  gap: 1px;
}

.searchable-multi-select__option strong {
  overflow: hidden;
  font-size: 12px;
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.searchable-multi-select__option small {
  overflow: hidden;
  color: #718096;
  font-size: 10.5px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
