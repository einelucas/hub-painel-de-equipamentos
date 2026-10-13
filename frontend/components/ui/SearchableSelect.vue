<script setup lang="ts">
import { Check, ChevronDown, Search } from "lucide-vue-next";
import { computed, ref, watch } from "vue";
import { useFloatingMenu } from "~/composables/useFloatingMenu";
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
    /** Ordena por rótulo; desligue para listas com ordem própria (ex.: etapas 0–8). */
    sorted?: boolean;
    /** Exibe a opção vazia (`emptyLabel`) no menu; desligue em campos obrigatórios. */
    clearable?: boolean;
    /** Validação nativa do formulário: bloqueia o envio sem uma opção escolhida. */
    required?: boolean;
  }>(),
  {
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
  /** Só quando o valor de fato muda (como o `change` de um select nativo). */
  change: [value: string];
}>();

const open = ref(false);
const query = ref("");
const activeIndex = ref(-1);
const control = ref<HTMLElement | null>(null);
const { style: menuStyle } = useFloatingMenu(control, open);
const selected = computed(() => props.options.find((item) => item.id === props.modelValue) ?? null);
const ordered = computed(() =>
  props.sorted
    ? [...props.options].sort((left, right) =>
        left.label.localeCompare(right.label, "pt-BR", { numeric: true, sensitivity: "base" }),
      )
    : props.options,
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
/** Itens navegáveis pelo teclado: a opção vazia (quando existe) e as filtradas. */
const navigable = computed<(SearchableOption | null)[]>(() =>
  props.clearable ? [null, ...filtered.value] : filtered.value,
);

watch(
  selected,
  (option) => {
    if (!open.value) query.value = option?.label ?? "";
  },
  { immediate: true },
);

function commit(value: string): void {
  const changed = value !== props.modelValue;
  emit("update:modelValue", value);
  if (changed) emit("change", value);
}

/** Digitar só busca: a seleção atual permanece até outra opção ser escolhida. */
function handleInput(event: Event): void {
  query.value = (event.target as HTMLInputElement).value;
  open.value = true;
  activeIndex.value = -1;
}

function choose(option: SearchableOption): void {
  commit(option.id);
  query.value = option.label;
  open.value = false;
}

function chooseEmpty(): void {
  commit(props.emptyValue);
  query.value = "";
  open.value = false;
}

function openMenu(): void {
  open.value = true;
  activeIndex.value = -1;
  if (selected.value) query.value = "";
}

function toggle(): void {
  if (props.disabled) return;
  if (open.value) close();
  else openMenu();
}

function close(): void {
  open.value = false;
  query.value = selected.value?.label ?? "";
}

function closeOnBlur(event: FocusEvent): void {
  const next = event.relatedTarget as Node | null;
  if (!(event.currentTarget as HTMLElement).contains(next)) close();
}

function move(step: number): void {
  if (!open.value) openMenu();
  const total = navigable.value.length;
  if (total === 0) return;
  activeIndex.value = (activeIndex.value + step + total) % total;
}

/** Enter só é consumido com uma opção destacada; senão segue o envio do formulário. */
function chooseActive(event: KeyboardEvent): void {
  if (!open.value || activeIndex.value < 0) return;
  event.preventDefault();
  const option = navigable.value[activeIndex.value];
  if (option === undefined) return;
  if (option === null) chooseEmpty();
  else choose(option);
}

function isActive(option: SearchableOption | null): boolean {
  return activeIndex.value >= 0 && navigable.value[activeIndex.value] === option;
}
</script>

<template>
  <div class="searchable-select" :class="{ 'searchable-select--disabled': disabled }" @focusout="closeOnBlur">
    <div ref="control" class="searchable-select__control">
      <Search :size="15" aria-hidden="true" />
      <input
        :value="query"
        :aria-label="label"
        :data-testid="testId"
        :disabled="disabled"
        :required="required"
        role="combobox"
        aria-autocomplete="list"
        :aria-expanded="open"
        :placeholder="modelValue === emptyValue ? emptyLabel : placeholder"
        @focus="openMenu"
        @input="handleInput"
        @keydown.esc="close"
        @keydown.down.prevent="move(1)"
        @keydown.up.prevent="move(-1)"
        @keydown.enter="chooseActive"
      >
      <button type="button" tabindex="-1" :disabled="disabled" :aria-label="`Abrir ${label}`" @click="toggle">
        <ChevronDown :size="16" />
      </button>
    </div>
    <!-- No body: o menu nunca é recortado nem cria rolagem no container (modais, cards). -->
    <Teleport to="body">
    <div v-if="open" class="searchable-select__menu" role="listbox" :style="menuStyle" @mousedown.prevent>
      <button
        v-if="clearable"
        type="button"
        role="option"
        tabindex="-1"
        :class="{ 'is-active': isActive(null) }"
        :aria-selected="modelValue === emptyValue"
        @mousedown.prevent="chooseEmpty"
      >
        <span><strong>{{ emptyLabel }}</strong></span>
        <Check v-if="modelValue === emptyValue" :size="15" />
      </button>
      <button
        v-for="option in filtered"
        :key="option.id"
        type="button"
        role="option"
        tabindex="-1"
        :class="{ 'is-active': isActive(option) }"
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
    </Teleport>
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
.searchable-select__menu { position: fixed; z-index: 200; overflow-y: auto; border: 1px solid #d8e1ec; border-radius: 9px; padding: 5px; background: #fff; box-shadow: 0 12px 28px rgb(30 50 78 / 16%); }
.searchable-select__menu button { display: flex; width: 100%; align-items: center; justify-content: space-between; gap: 8px; border: 0; border-radius: 7px; padding: 8px 9px; background: transparent; color: #263d5d; text-align: left; cursor: pointer; }
.searchable-select__menu button:hover, .searchable-select__menu button.is-active, .searchable-select__menu button[aria-selected="true"] { background: #eef4fb; }
.searchable-select__menu button.is-active { outline: 1px solid #b9cbe3; }
.searchable-select__menu span { display: grid; min-width: 0; gap: 1px; }
.searchable-select__menu strong { overflow: hidden; font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.searchable-select__menu small, .searchable-select__menu p { margin: 0; color: #718096; font-size: 10.5px; }
.searchable-select__menu p { padding: 10px; text-align: center; }
</style>
