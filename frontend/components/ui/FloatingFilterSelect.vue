<script setup lang="ts" generic="T extends string | string[] | null = string">
import { ElOption, ElSelect } from "element-plus";
import { computed, nextTick, onMounted, ref, watch } from "vue";
import type { Component } from "vue";
import type { SearchableOption } from "~/types/ui";

/**
 * Filtro select com Floating Label no padrão visual do Hub.
 *
 * O recorte real da borda é feito por um `fieldset/legend`: quando o campo está
 * ativo/preenchido, a `legend` ganha largura e o navegador interrompe a borda
 * superior ao redor do texto. A label visível é um elemento separado — como no
 * outlined input do Material — para poder animar do centro do campo até a
 * borda sem depender de posicionamento improvisado.
 *
 * O `ElSelect` continua responsável por teclado, acessibilidade, busca,
 * dropdown teleportado (popper) e estado de loading/disabled/clearable.
 */
const props = withDefaults(
  defineProps<{
    modelValue: T;
    label: string;
    options: SearchableOption[];
    /** Ícone lucide (ou qualquer componente Vue) exibido à esquerda. */
    icon?: Component;
    placeholder?: string;
    disabled?: boolean;
    loading?: boolean;
    clearable?: boolean;
    filterable?: boolean;
    multiple?: boolean;
    /** Opção vazia exibida no menu, como "Todas as áreas". */
    emptyLabel?: string;
    emptyValue?: string;
    /** Ordena por rótulo; desligue em listas com ordem própria (ex.: etapas). */
    sorted?: boolean;
    testId?: string;
    noDataText?: string;
    disabledText?: string;
  }>(),
  {
    icon: undefined,
    placeholder: "Digite para buscar",
    disabled: false,
    loading: false,
    clearable: true,
    filterable: true,
    multiple: false,
    emptyLabel: "",
    emptyValue: "",
    sorted: true,
    testId: undefined,
    noDataText: "Nenhuma opção encontrada.",
    disabledText: "Nenhuma opção disponível.",
  },
);

const emit = defineEmits<{
  "update:modelValue": [value: T];
  /** Só quando o valor de fato muda (como o `change` de um select nativo). */
  change: [value: T];
  focus: [event: FocusEvent];
  blur: [event: FocusEvent];
  "visible-change": [open: boolean];
}>();

const focused = ref(false);
const open = ref(false);
const query = ref("");
const root = ref<HTMLElement | null>(null);

const hasValue = computed(() => {
  if (props.multiple) {
    return Array.isArray(props.modelValue) && props.modelValue.length > 0;
  }
  return (
    props.modelValue !== null &&
    props.modelValue !== undefined &&
    String(props.modelValue) !== props.emptyValue
  );
});

const floating = computed(() => focused.value || open.value || hasValue.value);

const selectedOptions = computed(() => {
  const values = props.multiple
    ? (Array.isArray(props.modelValue) ? props.modelValue : [])
    : props.modelValue === null || props.modelValue === undefined
      ? []
      : [String(props.modelValue)];
  return props.options.filter((option) => values.includes(option.id));
});

const selectedLabel = computed(() =>
  selectedOptions.value.map((option) => option.label).join(", "),
);

const orderedOptions = computed(() =>
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
  if (!term) return orderedOptions.value;
  return orderedOptions.value.filter((option) =>
    [option.label, option.description, option.searchText]
      .filter(Boolean)
      .some((value) => String(value).toLocaleLowerCase("pt-BR").includes(term)),
  );
});

const controlPlaceholder = computed(() =>
  !hasValue.value && floating.value ? props.placeholder : "",
);

const rootAttrs = computed(() => ({
  "data-selected-label": selectedLabel.value,
  "data-disabled": props.disabled ? "true" : "false",
  "data-filled": hasValue.value ? "true" : "false",
  "data-floating": floating.value ? "true" : "false",
  "data-open": open.value ? "true" : "false",
}));

function normalize(value: unknown): T {
  if (props.multiple) {
    return (Array.isArray(value) ? value.map(String) : []) as T;
  }
  if (value === undefined || value === null || value === "") {
    return props.emptyValue as T;
  }
  return String(value) as T;
}

function sameValue(left: T, right: T): boolean {
  if (Array.isArray(left) && Array.isArray(right)) {
    return (
      left.length === right.length && left.every((item) => right.includes(item))
    );
  }
  return left === right;
}

function onUpdate(value: unknown): void {
  emit("update:modelValue", normalize(value));
}

function onChange(value: unknown): void {
  const next = normalize(value);
  if (sameValue(next, props.modelValue)) return;
  emit("change", next);
}

function onFocus(event: FocusEvent): void {
  focused.value = true;
  emit("focus", event);
}

function onBlur(event: FocusEvent): void {
  focused.value = false;
  emit("blur", event);
}

function onFilter(value: string): void {
  query.value = value;
}

function onVisibleChange(visible: boolean): void {
  open.value = visible;
  // Ao fechar, a próxima abertura volta a mostrar todas as opções.
  if (!visible) query.value = "";
  emit("visible-change", visible);
}

/**
 * Mantém o `data-testid` no input interno, como no SearchableSelect original.
 * Assim seletores de teste e ferramentas de acessibilidade encontram o mesmo
 * alvo de antes da migração para o padrão floating.
 */
function syncInputAttributes(): void {
  const input = root.value?.querySelector<HTMLInputElement>(".el-select__input");
  if (!input) return;
  if (props.testId) input.setAttribute("data-testid", props.testId);
  else input.removeAttribute("data-testid");
}

onMounted(syncInputAttributes);
watch(
  () => [props.testId, props.disabled] as const,
  () => {
    void nextTick(syncInputAttributes);
  },
  { flush: "post" },
);
</script>

<template>
  <div
    ref="root"
    class="floating-filter-select"
    :class="{
      'is-floating': floating,
      'is-focused': focused,
      'is-open': open,
      'is-filled': hasValue,
      'is-disabled': props.disabled,
      'has-icon': Boolean(props.icon),
    }"
    v-bind="rootAttrs"
  >
    <!-- fieldset/legend: o recorte da borda é nativo do navegador. -->
    <fieldset class="floating-filter-select__outline" aria-hidden="true">
      <legend class="floating-filter-select__legend">
        <span>{{ props.label }}</span>
      </legend>
    </fieldset>

    <span v-if="props.icon" class="floating-filter-select__icon" aria-hidden="true">
      <component :is="props.icon" :size="16" :stroke-width="1.9" />
    </span>

    <ElSelect
      :model-value="props.modelValue"
      :disabled="props.disabled"
      :loading="props.loading"
      :clearable="props.clearable"
      :multiple="props.multiple"
      :filterable="props.filterable"
      :placeholder="controlPlaceholder"
      :aria-label="props.label"
      automatic-dropdown
      :persistent="false"
      :fit-input-width="true"
      popper-class="hub-select-popper floating-filter-select__popper"
      :filter-method="onFilter"
      :no-data-text="props.disabled ? props.disabledText : props.noDataText"
      class="floating-filter-select__control"
      @update:model-value="onUpdate"
      @change="onChange"
      @focus="onFocus"
      @blur="onBlur"
      @visible-change="onVisibleChange"
    >
      <ElOption
        v-if="props.clearable && props.emptyLabel"
        :value="props.emptyValue"
        :label="props.emptyLabel"
      >
        <span><strong>{{ props.emptyLabel }}</strong></span>
      </ElOption>
      <ElOption
        v-for="option in filteredOptions"
        :key="option.id"
        :value="option.id"
        :label="option.label"
      >
        <span class="floating-filter-select__option">
          <strong>{{ option.label }}</strong>
          <small v-if="option.description">{{ option.description }}</small>
        </span>
      </ElOption>
    </ElSelect>

    <span class="floating-filter-select__label" aria-hidden="true">{{ props.label }}</span>
  </div>
</template>

<style scoped>
.floating-filter-select {
  --ffs-start: 14px;
  --ffs-label-start: 14px;
  --ffs-end: 34px;
  --ffs-border: #d8e0ea;
  --ffs-border-hover: #c2cedd;
  --ffs-text: #7a879a;
  --ffs-value: #26364d;
  --ffs-focus: var(--el-color-primary, #304f7e);

  position: relative;
  min-width: 0;
  height: 46px;
  color: var(--ffs-value);
  font-family: var(--el-font-family);
  font-size: 13.5px;
}

.has-icon { --ffs-start: 38px; }

/* ===== contorno (recorte real via fieldset/legend) ===== */
.floating-filter-select__outline {
  position: absolute;
  inset: 0;
  z-index: 0;
  min-width: 0;
  margin: 0;
  padding: 0;
  border: 1px solid var(--ffs-border);
  border-radius: 9px;
  background: #fff;
  pointer-events: none;
  transition:
    border-color 0.17s ease,
    box-shadow 0.17s ease,
    background-color 0.17s ease;
}

.floating-filter-select__legend {
  float: unset;
  display: block;
  width: auto;
  height: 12px;
  max-width: 0.01px;
  margin: 0 0 0 calc(var(--ffs-label-start) - 4px);
  padding: 0;
  overflow: hidden;
  font-size: 10.5px;
  font-weight: 600;
  line-height: 12px;
  visibility: hidden;
  transition: max-width 0.17s ease;
}

/*
 * A área reservada à label termina antes do ícone de abrir/limpar. Sem essa
 * trava, labels longas passam por baixo da seta — o texto continua visível no
 * DOM, mas parece colidir com o controle.
 */
.is-floating .floating-filter-select__legend {
  max-width: calc(100% - var(--ffs-label-start) - var(--ffs-end) - 12px);
}

.floating-filter-select__legend > span {
  display: inline-block;
  max-width: 100%;
  padding: 0 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  vertical-align: top;
}

.floating-filter-select:hover:not(.is-disabled):not(.is-focused) .floating-filter-select__outline {
  border-color: var(--ffs-border-hover);
}

.is-focused .floating-filter-select__outline,
.is-open .floating-filter-select__outline {
  border-color: var(--ffs-focus);
  box-shadow: 0 0 0 3px rgb(48 79 126 / 9%);
}

.is-disabled .floating-filter-select__outline {
  border-color: #e2e8f0;
  background: #f8fafc;
}

/* ===== label flutuante ===== */
.floating-filter-select__label {
  position: absolute;
  top: 50%;
  right: calc(var(--ffs-end) + 20px);
  left: var(--ffs-start);
  z-index: 3;
  overflow: hidden;
  color: var(--ffs-text);
  font-size: 13.5px;
  font-weight: 500;
  line-height: 1.2;
  text-overflow: ellipsis;
  white-space: nowrap;
  pointer-events: none;
  transform: translateY(-50%);
  transition:
    top 0.17s ease,
    font-size 0.17s ease,
    color 0.17s ease;
}

.is-floating .floating-filter-select__label {
  top: 0;
  right: calc(var(--ffs-end) + 12px);
  left: var(--ffs-label-start);
  color: #64748b;
  font-size: 10.5px;
  font-weight: 600;
}

.is-focused .floating-filter-select__label { color: var(--ffs-focus); }
.is-disabled .floating-filter-select__label { color: #a0aec0; }

/* ===== ícone esquerdo ===== */
.floating-filter-select__icon {
  position: absolute;
  top: 50%;
  left: 13px;
  z-index: 2;
  display: grid;
  place-items: center;
  color: #8793a5;
  pointer-events: none;
  transform: translateY(-50%);
  transition: color 0.17s ease;
}

.is-focused .floating-filter-select__icon,
.is-open .floating-filter-select__icon { color: var(--ffs-focus); }
.is-disabled .floating-filter-select__icon { color: #b6c0cd; }

/* ===== controle Element Plus sem a borda própria ===== */
.floating-filter-select__control {
  position: relative;
  z-index: 1;
  width: 100%;
}

.floating-filter-select__control :deep(.el-select__wrapper) {
  min-height: 46px;
  padding: 4px var(--ffs-end) 4px var(--ffs-start);
  border-radius: 9px;
  background: transparent;
  box-shadow: none;
}

.floating-filter-select__control :deep(.el-select__wrapper.is-hovering),
.floating-filter-select__control :deep(.el-select__wrapper.is-focused),
.floating-filter-select__control :deep(.el-select__wrapper.is-disabled) {
  background: transparent;
  box-shadow: none;
}

.floating-filter-select__control :deep(.el-select__selection) { min-width: 0; }

.floating-filter-select__control :deep(.el-select__selection.is-near) { margin-left: 0; }

.floating-filter-select__control :deep(.el-select__placeholder) {
  width: 100%;
  overflow: hidden;
  color: var(--ffs-value);
  font-size: 13.5px;
  font-weight: 500;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.floating-filter-select__control :deep(.el-select__placeholder.is-transparent) {
  color: #9aa6b5;
  font-weight: 400;
}

.floating-filter-select__control :deep(.el-select__selected-item) {
  min-width: 0;
  max-width: 100%;
}

.floating-filter-select__control :deep(.el-select__input-wrapper) { min-width: 0; }

.floating-filter-select__control :deep(.el-select__input) {
  color: var(--ffs-value);
  font-family: inherit;
  font-size: 13.5px;
}

.floating-filter-select__control :deep(.el-select__caret) {
  color: #94a3b8;
  font-size: 14px;
  transition:
    transform 0.17s ease,
    color 0.17s ease;
}

.is-open .floating-filter-select__control :deep(.el-select__caret) { color: var(--ffs-focus); }

.floating-filter-select__control :deep(.el-select__clear) { color: #94a3b8; }

.is-disabled .floating-filter-select__control :deep(.el-select__placeholder),
.is-disabled .floating-filter-select__control :deep(.el-select__input) {
  color: #9aa6b5;
}

@media (prefers-reduced-motion: reduce) {
  .floating-filter-select__outline,
  .floating-filter-select__legend,
  .floating-filter-select__label,
  .floating-filter-select__icon,
  .floating-filter-select__control :deep(.el-select__caret) {
    transition: none;
  }
}
</style>
