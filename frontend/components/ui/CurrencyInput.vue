<script setup lang="ts">
import { ref, watch } from "vue";
import {
  editableCurrencyInput,
  formatCurrencyInput,
  parseCurrencyInput,
} from "~/utils/currency";

const props = withDefaults(
  defineProps<{
    modelValue: string | number | null;
    label: string;
    testId?: string;
    disabled?: boolean;
    required?: boolean;
    placeholder?: string;
  }>(),
  {
    testId: undefined,
    disabled: false,
    required: false,
    placeholder: "R$ 0,00",
  },
);

const emit = defineEmits<{
  "update:modelValue": [value: string];
}>();

const focused = ref(false);
const display = ref(formatCurrencyInput(props.modelValue));

watch(
  () => props.modelValue,
  (value) => {
    if (!focused.value) display.value = formatCurrencyInput(value);
  },
);

function onFocus(): void {
  focused.value = true;
  display.value = editableCurrencyInput(props.modelValue);
}

function onInput(value: string | null): void {
  const raw = String(value ?? "").replace(/[^\d,.]/g, "");
  display.value = raw;
  emit("update:modelValue", parseCurrencyInput(raw));
}

function onBlur(): void {
  focused.value = false;
  const normalized = parseCurrencyInput(display.value);
  display.value = formatCurrencyInput(normalized);
}
</script>

<template>
  <VTextField
    :model-value="display"
    type="text"
    inputmode="decimal"
    autocomplete="off"
    :label="label"
    :data-testid="testId"
    :disabled="disabled"
    :required="required"
    :placeholder="placeholder"
    persistent-placeholder
    @focus="onFocus"
    @update:model-value="onInput"
    @blur="onBlur"
  />
</template>
