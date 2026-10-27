<script setup lang="ts">
import { ElOption, ElSelect } from "element-plus";
import { computed, nextTick, onMounted, ref, watch } from "vue";
import type { SearchableOption } from "~/types/ui";

/**
 * Select pesquisável do Hub. O `ElSelect` cuida de foco, teclado, dropdown
 * teleportado e acessibilidade; a busca continua cobrindo rótulo, descrição e
 * `searchText`, sem apagar a seleção enquanto o usuário digita.
 */
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

const root = ref<HTMLElement | null>(null);
const query = ref("");
const selected = computed(
  () => props.options.find((item) => item.id === props.modelValue) ?? null,
);
const ordered = computed(() =>
  props.sorted
    ? [...props.options].sort((left, right) =>
        left.label.localeCompare(right.label, "pt-BR", {
          numeric: true,
          sensitivity: "base",
        }),
      )
    : props.options,
);
const filteredOptions = computed(() => {
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
const selectedLabel = computed(() => selected.value?.label ?? "");
const isEmpty = computed(() => props.modelValue === props.emptyValue);
const wrapperAttrs = computed(() => ({
  "data-selected-label": selectedLabel.value,
  "data-disabled": props.disabled ? "true" : "false",
  "data-required": props.required ? "true" : "false",
  "data-placeholder": isEmpty.value ? props.emptyLabel : props.placeholder,
}));

function normalize(value: unknown): string {
  if (value === undefined || value === null) return props.emptyValue;
  return String(value);
}

function onUpdate(value: unknown): void {
  emit("update:modelValue", normalize(value));
}

function onChange(value: unknown): void {
  const next = normalize(value);
  clearInvalidState();
  // O ElSelect emite `change` também ao reescolher o mesmo valor; o contrato
  // anterior só avisava quando o valor realmente mudava.
  if (next === props.modelValue) return;
  emit("change", next);
}

/** O ElSelect não expõe `required`; sincronizamos o estado no input interno. */
function selectInput(): HTMLInputElement | null {
  return root.value?.querySelector<HTMLInputElement>(".el-select__input") ?? null;
}

function syncAria(): void {
  const input = selectInput();
  if (!input) return;
  if (props.required) input.setAttribute("aria-required", "true");
  else input.removeAttribute("aria-required");
  // Mantém o `data-testid` no input, como no componente anterior.
  if (props.testId) input.setAttribute("data-testid", props.testId);
  else input.removeAttribute("data-testid");
}

function clearInvalidState(): void {
  selectInput()?.removeAttribute("aria-invalid");
}

function onInvalid(event: Event): void {
  event.preventDefault();
  const input = selectInput();
  input?.setAttribute("aria-invalid", "true");
  input?.focus();
}

function onFilter(value: string): void {
  query.value = value;
}

function onVisibleChange(open: boolean): void {
  // Ao fechar, a próxima abertura volta a mostrar todas as opções.
  if (!open) query.value = "";
}

onMounted(syncAria);
watch(
  () => [props.required, props.disabled, props.testId] as const,
  () => {
    void nextTick(syncAria);
  },
);
</script>

<template>
  <div ref="root" class="searchable-select" v-bind="wrapperAttrs">
    <!-- Campo nativo oculto: participa da validação do formulário e mantém o
         bloqueio de envio obrigatório mesmo com o select do Element Plus. -->
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
    <ElSelect
      :model-value="props.modelValue"
      :disabled="props.disabled"
      :placeholder="isEmpty ? props.emptyLabel : props.placeholder"
      :clearable="props.clearable"
      :aria-label="props.label"
      filterable
      automatic-dropdown
      :persistent="false"
      :fit-input-width="true"
      popper-class="hub-select-popper"
      :filter-method="onFilter"
      :no-data-text="'Nenhuma opção encontrada.'"
      class="searchable-select__control"
      @update:model-value="onUpdate"
      @change="onChange"
      @visible-change="onVisibleChange"
    >
      <ElOption
        v-if="props.clearable"
        :value="props.emptyValue"
        :label="props.emptyLabel"
        class="searchable-select__empty-option"
      >
        <span><strong>{{ props.emptyLabel }}</strong></span>
      </ElOption>
      <ElOption
        v-for="option in filteredOptions"
        :key="option.id"
        :value="option.id"
        :label="option.label"
      >
        <span class="searchable-select__option">
          <strong>{{ option.label }}</strong>
          <small v-if="option.description">{{ option.description }}</small>
        </span>
      </ElOption>
    </ElSelect>
  </div>
</template>

<style scoped>
.searchable-select {
  position: relative;
  min-width: 0;
}

.searchable-select__required {
  position: absolute;
  width: 1px;
  height: 1px;
  margin: -1px;
  padding: 0;
  overflow: hidden;
  border: 0;
  opacity: 0;
  pointer-events: none;
}

.searchable-select__option { display: grid; gap: 2px; }
.searchable-select__option small { color: var(--el-text-color-secondary); font-size: 12px; }
</style>
