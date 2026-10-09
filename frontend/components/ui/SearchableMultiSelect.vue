<script setup lang="ts">
import { Check, ChevronDown, Search, X } from "lucide-vue-next";
import { computed, ref } from "vue";
import type { SearchableOption } from "~/types/ui";

const props = withDefaults(
  defineProps<{
    options: SearchableOption[];
    modelValue: string[];
    label: string;
    placeholder?: string;
    disabled?: boolean;
    disabledMessage?: string;
  }>(),
  {
    placeholder: "Digite para buscar",
    disabled: false,
    disabledMessage: "Nenhuma opção disponível.",
  },
);
const emit = defineEmits<{ "update:modelValue": [value: string[]] }>();
const open = ref(false);
const query = ref("");
const ordered = computed(() =>
  [...props.options].sort((left, right) =>
    left.label.localeCompare(right.label, "pt-BR", { numeric: true, sensitivity: "base" }),
  ),
);
const selected = computed(() => ordered.value.filter((item) => props.modelValue.includes(item.id)));
const filtered = computed(() => {
  const term = query.value.trim().toLocaleLowerCase("pt-BR");
  if (!term) return ordered.value;
  return ordered.value.filter((option) =>
    [option.label, option.description, option.searchText]
      .filter(Boolean)
      .some((value) => String(value).toLocaleLowerCase("pt-BR").includes(term)),
  );
});

function toggleOption(id: string): void {
  emit(
    "update:modelValue",
    props.modelValue.includes(id)
      ? props.modelValue.filter((item) => item !== id)
      : [...props.modelValue, id],
  );
}

function closeOnBlur(event: FocusEvent): void {
  const next = event.relatedTarget as Node | null;
  if (!(event.currentTarget as HTMLElement).contains(next)) open.value = false;
}
</script>

<template>
  <div class="multi-select" :class="{ 'multi-select--disabled': disabled }" @focusout="closeOnBlur">
    <div v-if="selected.length" class="multi-select__chips">
      <span
        v-for="option in selected"
        :key="option.id"
        :title="option.description || undefined"
      >
        {{ option.label }}
        <button type="button" :aria-label="`Remover ${option.label}`" @click="toggleOption(option.id)"><X :size="12" /></button>
      </span>
    </div>
    <div class="multi-select__control">
      <Search :size="15" aria-hidden="true" />
      <input
        v-model="query"
        :aria-label="label"
        :disabled="disabled"
        role="combobox"
        aria-autocomplete="list"
        :aria-expanded="open"
        :placeholder="selected.length ? 'Adicionar outro' : placeholder"
        @focus="open = true"
        @keydown.esc="open = false"
      >
      <button type="button" :disabled="disabled" :aria-label="`Abrir ${label}`" @click="open = !open">
        <ChevronDown :size="16" />
      </button>
    </div>
    <div v-if="open" class="multi-select__menu" role="listbox" aria-multiselectable="true">
      <button
        v-for="option in filtered"
        :key="option.id"
        type="button"
        role="option"
        :aria-selected="modelValue.includes(option.id)"
        @mousedown.prevent="toggleOption(option.id)"
      >
        <span class="multi-select__check"><Check v-if="modelValue.includes(option.id)" :size="13" /></span>
        <span class="multi-select__option">
          <strong>{{ option.label }}</strong>
          <small v-if="option.description">{{ option.description }}</small>
        </span>
      </button>
      <p v-if="disabled">{{ disabledMessage }}</p>
      <p v-else-if="filtered.length === 0">Nenhuma opção encontrada.</p>
    </div>
  </div>
</template>

<style scoped>
.multi-select { position: relative; border: 1px solid #d8e1ec; border-radius: 9px; background: #fff; }
.multi-select:focus-within { border-color: #5277aa; box-shadow: 0 0 0 2px rgb(82 119 170 / 12%); }
.multi-select__chips { display: flex; flex-wrap: wrap; gap: 5px; padding: 8px 8px 0; }
.multi-select__chips > span { display: inline-flex; max-width: 100%; align-items: center; gap: 4px; border-radius: 6px; padding: 4px 5px 4px 8px; background: #eef4fb; color: #315889; font-size: 10.5px; font-weight: 750; }
.multi-select__chips button, .multi-select__control button { display: grid; border: 0; padding: 3px; background: transparent; color: inherit; cursor: pointer; place-items: center; }
.multi-select__control { display: flex; min-height: 38px; align-items: center; gap: 7px; padding: 0 8px; color: #718096; }
.multi-select__control input { min-width: 0; flex: 1; border: 0; outline: 0; padding: 9px 0; background: transparent; color: #263d5d; font-size: 12px; }
.multi-select--disabled { background: #f6f7f9; color: #9ca5b4; }
.multi-select__menu { position: absolute; z-index: 30; top: calc(100% + 4px); right: 0; left: 0; max-height: 230px; overflow-y: auto; border: 1px solid #d8e1ec; border-radius: 9px; padding: 5px; background: #fff; box-shadow: 0 12px 28px rgb(30 50 78 / 16%); }
.multi-select__menu > button { display: flex; width: 100%; align-items: center; gap: 8px; border: 0; border-radius: 7px; padding: 8px 9px; background: transparent; color: #263d5d; text-align: left; cursor: pointer; }
.multi-select__menu > button:hover, .multi-select__menu > button[aria-selected="true"] { background: #eef4fb; }
.multi-select__check { display: grid; width: 16px; height: 16px; flex: 0 0 16px; border: 1px solid #aeb9c8; border-radius: 4px; color: #fff; place-items: center; }
.multi-select__menu > button[aria-selected="true"] .multi-select__check { border-color: #315889; background: #315889; }
.multi-select__option { display: grid; min-width: 0; gap: 1px; }
.multi-select__option strong { font-size: 12px; }
.multi-select__option small, .multi-select__menu p { margin: 0; color: #718096; font-size: 10.5px; }
.multi-select__menu p { padding: 10px; text-align: center; }
</style>
