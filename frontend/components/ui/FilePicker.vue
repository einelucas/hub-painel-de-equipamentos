<script setup lang="ts">
import { mdiUpload } from "@mdi/js";
import { computed, ref } from "vue";
import { VBtn } from "vuetify/components";

/**
 * Seletor de arquivo do Hub: botão visível + input oculto. Os envios em si
 * continuam centralizados no `useApi`/Axios (com `onUploadProgress`); o
 * componente só escolhe o arquivo e emite para o dono do fluxo.
 */
const props = withDefaults(
  defineProps<{
    modelValue?: File | null;
    /** Atributo `accept` do input (ex.: ".xlsx"). */
    accept?: string;
    disabled?: boolean;
    /** Texto do botão quando não há arquivo escolhido. */
    label?: string;
    /** Nome já enviado ao servidor (edição), mostrado quando não há arquivo novo. */
    currentLabel?: string;
    /** Vai para o input oculto (os testes usam para injetar `files`). */
    testId?: string;
  }>(),
  {
    modelValue: null,
    accept: "",
    disabled: false,
    label: "Selecionar arquivo",
    currentLabel: "",
    testId: undefined,
  },
);
const emit = defineEmits<{
  "update:modelValue": [value: File | null];
  /** Toda mudança de seleção (inclusive limpar o campo). */
  change: [value: File | null];
}>();

const input = ref<HTMLInputElement | null>(null);

const shown = computed(
  () => props.modelValue?.name ?? (props.currentLabel || props.label),
);

function choose(): void {
  if (props.disabled) return;
  input.value?.click();
}

function onFiles(event: Event): void {
  const target = event.target as HTMLInputElement;
  const picked = target.files?.[0] ?? null;
  emit("update:modelValue", picked);
  emit("change", picked);
  // Permite reescolher o mesmo arquivo depois (o input fica limpo).
  target.value = "";
}
</script>

<template>
  <span class="file-picker">
    <VBtn
      type="button"
      variant="outlined"
      class="file-picker__button"
      :disabled="props.disabled"
      :prepend-icon="mdiUpload"
     @click="choose">

      <span class="file-picker__name">{{ shown }}</span>
    </VBtn>
    <input
      ref="input"
      class="file-picker__input"
      type="file"
      :accept="props.accept || undefined"
      :disabled="props.disabled"
      :data-testid="props.testId"
      @change="onFiles"
    >
  </span>
</template>

<style scoped>
.file-picker {
  position: relative;
  display: inline-flex;
  min-width: 0;
}

.file-picker__button {
  justify-content: flex-start;
  gap: 7px;
  max-width: 100%;
}

.file-picker__name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-picker__input {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
  white-space: nowrap;
}
</style>
