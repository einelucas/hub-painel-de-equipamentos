<script setup lang="ts">
import { Check, ChevronDown, Search } from "lucide-vue-next";
import { computed, ref, watch } from "vue";
import type { Supplier } from "~/types/equipment";
import { sortSuppliers, supplierLabel } from "~/utils/suppliers";

const props = defineProps<{
  suppliers: Supplier[];
  modelValue: string;
  label: string;
}>();
const emit = defineEmits<{ "update:modelValue": [value: string] }>();

const open = ref(false);
const query = ref("");
const selected = computed(() => props.suppliers.find((item) => item.id === props.modelValue) ?? null);
const filtered = computed(() => {
  const term = query.value.trim().toLocaleLowerCase("pt-BR");
  const ordered = sortSuppliers(props.suppliers);
  if (!term) return ordered;
  return ordered.filter((supplier) =>
    [supplier.corporateCode, supplier.legalName, supplier.tradeName]
      .filter(Boolean)
      .some((value) => String(value).toLocaleLowerCase("pt-BR").includes(term)),
  );
});

watch(
  selected,
  (supplier) => {
    if (!open.value) query.value = supplier ? supplierLabel(supplier) : "";
  },
  { immediate: true },
);

function handleInput(event: Event): void {
  query.value = (event.target as HTMLInputElement).value;
  open.value = true;
  if (selected.value && query.value !== supplierLabel(selected.value)) emit("update:modelValue", "");
}

function choose(supplier: Supplier): void {
  emit("update:modelValue", supplier.id);
  query.value = supplierLabel(supplier);
  open.value = false;
}

function clear(): void {
  emit("update:modelValue", "__NONE__");
  query.value = "";
  open.value = false;
}

function closeOnBlur(event: FocusEvent): void {
  const next = event.relatedTarget as Node | null;
  if (!(event.currentTarget as HTMLElement).contains(next)) open.value = false;
}
</script>

<template>
  <div class="supplier-combobox" @focusout="closeOnBlur">
    <div class="supplier-combobox__control">
      <Search :size="15" aria-hidden="true" />
      <input
        :value="query"
        :aria-label="label"
        role="combobox"
        aria-autocomplete="list"
        :aria-expanded="open"
        placeholder="Digite o código ou nome"
        @focus="open = true"
        @input="handleInput"
        @keydown.esc="open = false"
      >
      <button type="button" :aria-label="`Abrir ${label}`" @click="open = !open">
        <ChevronDown :size="16" />
      </button>
    </div>
    <div v-if="open" class="supplier-combobox__menu" role="listbox">
      <button type="button" role="option" :aria-selected="modelValue === '__NONE__'" @mousedown.prevent="clear">
        <span><strong>Manter sem fornecedor</strong></span>
        <Check v-if="modelValue === '__NONE__'" :size="15" />
      </button>
      <button
        v-for="supplier in filtered"
        :key="supplier.id"
        type="button"
        role="option"
        :aria-selected="modelValue === supplier.id"
        @mousedown.prevent="choose(supplier)"
      >
        <span>
          <strong>{{ supplier.legalName }}</strong>
          <small>{{ supplier.corporateCode ? `Código ${supplier.corporateCode}` : "Sem código" }}</small>
        </span>
        <Check v-if="modelValue === supplier.id" :size="15" />
      </button>
      <p v-if="filtered.length === 0">Nenhum fornecedor encontrado.</p>
    </div>
  </div>
</template>

<style scoped>
.supplier-combobox { position: relative; min-width: 0; }
.supplier-combobox__control { display: flex; align-items: center; gap: 7px; border: 1px solid #d8e1ec; border-radius: 8px; padding: 0 8px; background: #fff; color: #718096; }
.supplier-combobox__control:focus-within { border-color: #5277aa; box-shadow: 0 0 0 2px rgb(82 119 170 / 12%); }
.supplier-combobox__control input { min-width: 0; flex: 1; border: 0; outline: 0; padding: 9px 0; background: transparent; color: #263d5d; font-size: 12px; }
.supplier-combobox__control button { display: grid; border: 0; padding: 5px; background: transparent; color: #52657c; cursor: pointer; place-items: center; }
.supplier-combobox__menu { position: absolute; z-index: 20; top: calc(100% + 4px); right: 0; left: 0; max-height: 230px; overflow-y: auto; border: 1px solid #d8e1ec; border-radius: 9px; padding: 5px; background: #fff; box-shadow: 0 12px 28px rgb(30 50 78 / 16%); }
.supplier-combobox__menu button { display: flex; width: 100%; align-items: center; justify-content: space-between; gap: 8px; border: 0; border-radius: 7px; padding: 8px 9px; background: transparent; color: #263d5d; text-align: left; cursor: pointer; }
.supplier-combobox__menu button:hover, .supplier-combobox__menu button[aria-selected="true"] { background: #eef4fb; }
.supplier-combobox__menu span { display: grid; min-width: 0; gap: 1px; }
.supplier-combobox__menu strong { overflow: hidden; font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.supplier-combobox__menu small, .supplier-combobox__menu p { margin: 0; color: #718096; font-size: 10.5px; }
.supplier-combobox__menu p { padding: 10px; text-align: center; }
</style>
