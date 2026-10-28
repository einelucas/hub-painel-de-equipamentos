<script setup lang="ts">
import { computed, ref } from "vue";
import type { Component } from "vue";
import { X } from "lucide-vue-next";

const props = withDefaults(defineProps<{
  modelValue: string;
  label: string;
  placeholder?: string;
  icon?: Component;
  disabled?: boolean;
  clearable?: boolean;
  testId?: string;
}>(), {
  placeholder: "Digite para buscar",
  icon: undefined,
  disabled: false,
  clearable: true,
  testId: undefined,
});

const emit = defineEmits<{
  "update:modelValue": [value: string];
  focus: [event: FocusEvent];
  blur: [event: FocusEvent];
  clear: [];
}>();

const focused = ref(false);
const hasValue = computed(() => Boolean(props.modelValue));
const floating = computed(() => focused.value || hasValue.value);
const controlPlaceholder = computed(() => floating.value && !hasValue.value ? props.placeholder : "");

function onInput(event: Event): void {
  emit("update:modelValue", (event.target as HTMLInputElement).value);
}

function onFocus(event: FocusEvent): void {
  focused.value = true;
  emit("focus", event);
}

function onBlur(event: FocusEvent): void {
  focused.value = false;
  emit("blur", event);
}

function clear(): void {
  emit("update:modelValue", "");
  emit("clear");
}
</script>

<template>
  <div
    class="floating-filter-input"
    :class="{
      'is-floating': floating,
      'is-focused': focused,
      'is-filled': hasValue,
      'is-disabled': props.disabled,
      'has-icon': Boolean(props.icon),
      'is-clearable': props.clearable,
    }"
    :data-filled="hasValue ? 'true' : 'false'"
    :data-floating="floating ? 'true' : 'false'"
  >
    <fieldset class="floating-filter-input__outline" aria-hidden="true">
      <legend class="floating-filter-input__legend"><span>{{ props.label }}</span></legend>
    </fieldset>

    <span v-if="props.icon" class="floating-filter-input__icon" aria-hidden="true">
      <component :is="props.icon" :size="16" :stroke-width="1.9" />
    </span>

    <input
      :value="props.modelValue"
      :placeholder="controlPlaceholder"
      :disabled="props.disabled"
      :aria-label="props.label"
      :data-testid="props.testId"
      class="floating-filter-input__control"
      type="text"
      @input="onInput"
      @focus="onFocus"
      @blur="onBlur"
    >

    <button
      v-if="props.clearable && hasValue && !props.disabled"
      class="floating-filter-input__clear"
      type="button"
      :aria-label="`Limpar ${props.label.toLowerCase()}`"
      @mousedown.prevent
      @click="clear"
    >
      <X :size="14" aria-hidden="true" />
    </button>

    <span class="floating-filter-input__label" aria-hidden="true">{{ props.label }}</span>
  </div>
</template>

<style scoped>
.floating-filter-input {
  --ffi-start: 14px;
  --ffi-label-start: 14px;
  --ffi-end: 15px;
  --ffi-border: #d8e0ea;
  --ffi-border-hover: #c2cedd;
  --ffi-text: #7a879a;
  --ffi-value: #26364d;
  --ffi-focus: var(--el-color-primary, #304f7e);

  position: relative;
  width: 100%;
  min-width: 0;
  height: 46px;
  color: var(--ffi-value);
  font-family: var(--el-font-family);
  font-size: 13.5px;
}

.has-icon { --ffi-start: 38px; }
.is-clearable { --ffi-end: 38px; }

.floating-filter-input__outline {
  position: absolute;
  inset: 0;
  z-index: 0;
  min-width: 0;
  margin: 0;
  padding: 0;
  border: 1px solid var(--ffi-border);
  border-radius: 8px;
  background: #fff;
  pointer-events: none;
  transition: border-color 0.17s ease, box-shadow 0.17s ease, background-color 0.17s ease;
}

.floating-filter-input__legend {
  float: unset;
  display: block;
  width: auto;
  height: 12px;
  max-width: 0.01px;
  margin: 0 0 0 calc(var(--ffi-label-start) - 4px);
  padding: 0;
  overflow: hidden;
  font-size: 10.5px;
  font-weight: 600;
  line-height: 12px;
  visibility: hidden;
  transition: max-width 0.17s ease;
}

.is-floating .floating-filter-input__legend {
  max-width: calc(100% - var(--ffi-label-start) - var(--ffi-end) - 12px);
}

.floating-filter-input__legend > span {
  display: inline-block;
  max-width: 100%;
  padding: 0 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  vertical-align: top;
}

.floating-filter-input:hover:not(.is-disabled):not(.is-focused) .floating-filter-input__outline {
  border-color: var(--ffi-border-hover);
}

.is-focused .floating-filter-input__outline {
  border-color: var(--ffi-focus);
  box-shadow: 0 0 0 3px rgb(48 79 126 / 9%);
}

.is-disabled .floating-filter-input__outline {
  border-color: #e2e8f0;
  background: #f8fafc;
}

.floating-filter-input__label {
  position: absolute;
  top: 50%;
  right: calc(var(--ffi-end) + 20px);
  left: var(--ffi-start);
  z-index: 3;
  overflow: hidden;
  color: var(--ffi-text);
  font-size: 13.5px;
  font-weight: 500;
  line-height: 1.2;
  text-overflow: ellipsis;
  white-space: nowrap;
  pointer-events: none;
  transform: translateY(-50%);
  transition: top 0.17s ease, font-size 0.17s ease, color 0.17s ease;
}

.is-floating .floating-filter-input__label {
  top: 0;
  right: calc(var(--ffi-end) + 12px);
  left: var(--ffi-label-start);
  color: #64748b;
  font-size: 10.5px;
  font-weight: 600;
}

.is-focused .floating-filter-input__label { color: var(--ffi-focus); }
.is-disabled .floating-filter-input__label { color: #a0aec0; }

.floating-filter-input__icon {
  position: absolute;
  top: 50%;
  left: 13px;
  z-index: 2;
  display: grid;
  place-items: center;
  color: #8793a5;
  pointer-events: none;
  transform: translateY(-50%);
}

.is-focused .floating-filter-input__icon { color: var(--ffi-focus); }
.is-disabled .floating-filter-input__icon { color: #b6c0cd; }

.floating-filter-input__control {
  position: relative;
  z-index: 1;
  width: 100%;
  height: 46px;
  box-sizing: border-box;
  border: 0;
  border-radius: 8px;
  padding: 4px var(--ffi-end) 4px var(--ffi-start);
  background: transparent;
  color: var(--ffi-value);
  font: inherit;
  font-weight: 500;
  outline: none;
}

.floating-filter-input__control::placeholder { color: #9aa6b5; font-weight: 400; }
.floating-filter-input__control:disabled { color: #9aa6b5; cursor: not-allowed; }

.floating-filter-input__clear {
  position: absolute;
  top: 50%;
  right: 11px;
  z-index: 4;
  display: grid;
  width: 24px;
  height: 24px;
  place-items: center;
  border: 0;
  padding: 0;
  background: transparent;
  color: #94a3b8;
  cursor: pointer;
  transform: translateY(-50%);
}

.floating-filter-input__clear:hover { color: var(--ffi-focus); }

@media (prefers-reduced-motion: reduce) {
  .floating-filter-input__outline,
  .floating-filter-input__legend,
  .floating-filter-input__label { transition: none; }
}
</style>
