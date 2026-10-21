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

function onFocus(event: FocusEvent): void {
  focused.value = true;
  const input = event.target as HTMLInputElement;
  display.value = editableCurrencyInput(props.modelValue);
  input.value = display.value;
}

function onInput(event: Event): void {
  const input = event.target as HTMLInputElement;
  const raw = input.value.replace(/[^\d,.]/g, "");
  input.value = raw;
  display.value = raw;
  emit("update:modelValue", parseCurrencyInput(raw));
}

function onBlur(event: FocusEvent): void {
  focused.value = false;
  const input = event.target as HTMLInputElement;
  const normalized = parseCurrencyInput(input.value);
  display.value = formatCurrencyInput(normalized);
  input.value = display.value;
}
</script>

<template>
  <input
    :value="display"
    type="text"
    inputmode="decimal"
    autocomplete="off"
    :aria-label="label"
    :data-testid="testId"
    :disabled="disabled"
    :required="required"
    :placeholder="placeholder"
    @focus="onFocus"
    @input="onInput"
    @blur="onBlur"
  >
</template>
