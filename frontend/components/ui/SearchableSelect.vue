<script setup lang="ts">
import { Check, ChevronDown, Search } from "lucide-vue-next";
import { computed, ref, watch } from "vue";
import type { SearchableOption } from "~/types/ui";

const props = withDefaults(
  defineProps<{
    options: SearchableOption[];
    modelValue: string;
    label: string;
    placeholder?: string;
    emptyLabel?: string;
    emptyValue?: string;
    disabled?: boolean;
    testId?: string;
  }>(),
  {
    placeholder: "Digite para buscar",
    emptyLabel: "Não informado",
    emptyValue: "",
    disabled: false,
    testId: undefined,
  },
);
const emit = defineEmits<{ "update:modelValue": [value: string] }>();

const open = ref(false);
const query = ref("");
const selected = computed(() => props.options.find((item) => item.id === props.modelValue) ?? null);
const ordered = computed(() =>
  [...props.options].sort((left, right) =>
    left.label.localeCompare(right.label, "pt-BR", { numeric: true, sensitivity: "base" }),
  ),
);
const filtered = computed(() => {
  const term = query.value.trim().toLocaleLowerCase("pt-BR");
  if (!term) return ordered.value;
  return ordered.value.filter((option) =>
    [option.label, option.description, option.searchText]
      .filter(Boolean)
      .some((value) => String(value).toLocaleLowerCase("pt-BR").includes(term)),
  );
});

watch(
  [selected, () => props.modelValue],
  ([option, value]) => {
    if (!open.value) query.value = option?.label ?? (value === props.emptyValue ? "" : "");
  },
  { immediate: true },
);

function handleInput(event: Event): void {
  query.value = (event.target as HTMLInputElement).value;
  open.value = true;
  if (selected.value && query.value !== selected.value.label) emit("update:modelValue", "");
}

function choose(option: SearchableOption): void {
  emit("update:modelValue", option.id);
  query.value = option.label;
  open.value = false;
}

function chooseEmpty(): void {
  emit("update:modelValue", props.emptyValue);
  query.value = "";
  open.value = false;
}

function toggle(): void {
  if (props.disabled) return;
  open.value = !open.value;
  if (open.value && selected.value) query.value = "";
  if (!open.value) query.value = selected.value?.label ?? "";
}

function focus(): void {
  open.value = true;
  if (selected.value) query.value = "";
}

function close(): void {
  open.value = false;
  query.value = selected.value?.label ?? "";
}

function closeOnBlur(event: FocusEvent): void {
  const next = event.relatedTarget as Node | null;
  if (!(event.currentTarget as HTMLElement).contains(next)) close();
}
</script>

<template>
  <div class="searchable-select" :class="{ 'searchable-select--disabled': disabled }" @focusout="closeOnBlur">
    <div class="searchable-select__control">
      <Search :size="15" aria-hidden="true" />
      <input
        :value="query"
        :aria-label="label"
        :data-testid="testId"
        :disabled="disabled"
        role="combobox"
        aria-autocomplete="list"
        :aria-expanded="open"
        :placeholder="modelValue === emptyValue ? emptyLabel : placeholder"
        @focus="focus"
        @input="handleInput"
        @keydown.esc="close"
      >
      <button type="button" :disabled="disabled" :aria-label="`Abrir ${label}`" @click="toggle">
        <ChevronDown :size="16" />
      </button>
    </div>
    <div v-if="open" class="searchable-select__menu" role="listbox">
      <button type="button" role="option" :aria-selected="modelValue === emptyValue" @mousedown.prevent="chooseEmpty">
        <span><strong>{{ emptyLabel }}</strong></span>
        <Check v-if="modelValue === emptyValue" :size="15" />
      </button>
      <button
        v-for="option in filtered"
        :key="option.id"
        type="button"
        role="option"
        :aria-selected="modelValue === option.id"
        @mousedown.prevent="choose(option)"
      >
        <span>
          <strong>{{ option.label }}</strong>
          <small v-if="option.description">{{ option.description }}</small>
        </span>
        <Check v-if="modelValue === option.id" :size="15" />
      </button>
      <p v-if="filtered.length === 0">Nenhuma opção encontrada.</p>
    </div>
  </div>
</template>

<style scoped>
.searchable-select { position: relative; min-width: 0; }
.searchable-select__control { display: flex; min-height: 39px; align-items: center; gap: 7px; border: 1px solid #d8e1ec; border-radius: 8px; padding: 0 8px; background: #fff; color: #718096; }
.searchable-select__control:focus-within { border-color: #5277aa; box-shadow: 0 0 0 2px rgb(82 119 170 / 12%); }
.searchable-select__control input { min-width: 0; flex: 1; border: 0; outline: 0; padding: 9px 0; background: transparent; color: #263d5d; font-size: 12px; }
.searchable-select__control button { display: grid; border: 0; padding: 5px; background: transparent; color: #52657c; cursor: pointer; place-items: center; }
.searchable-select--disabled .searchable-select__control { background: #f6f7f9; color: #9ca5b4; }
.searchable-select__control button:disabled { cursor: not-allowed; }
.searchable-select__menu { position: absolute; z-index: 30; top: calc(100% + 4px); right: 0; left: 0; max-height: 230px; overflow-y: auto; border: 1px solid #d8e1ec; border-radius: 9px; padding: 5px; background: #fff; box-shadow: 0 12px 28px rgb(30 50 78 / 16%); }
.searchable-select__menu button { display: flex; width: 100%; align-items: center; justify-content: space-between; gap: 8px; border: 0; border-radius: 7px; padding: 8px 9px; background: transparent; color: #263d5d; text-align: left; cursor: pointer; }
.searchable-select__menu button:hover, .searchable-select__menu button[aria-selected="true"] { background: #eef4fb; }
.searchable-select__menu span { display: grid; min-width: 0; gap: 1px; }
.searchable-select__menu strong { overflow: hidden; font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.searchable-select__menu small, .searchable-select__menu p { margin: 0; color: #718096; font-size: 10.5px; }
.searchable-select__menu p { padding: 10px; text-align: center; }
</style>
