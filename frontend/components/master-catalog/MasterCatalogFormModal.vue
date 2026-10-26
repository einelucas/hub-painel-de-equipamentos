<script setup lang="ts">
import { ref, useId, watch } from "vue";
import { Check, Info, X } from "lucide-vue-next";
import AppModal from "~/components/ui/AppModal.vue";
import Button from "~/components/ui/Button.vue";

const props = withDefaults(
  defineProps<{
    open: boolean;
    title: string;
    label: string;
    initialValue?: string;
    placeholder?: string;
    maxLength?: number;
    confirmLabel?: string;
    busy?: boolean;
    error?: string;
    hint?: string;
  }>(),
  {
    initialValue: "",
    placeholder: "",
    maxLength: 200,
    confirmLabel: "Salvar",
    busy: false,
    error: "",
    hint: "",
  },
);

const emit = defineEmits<{
  close: [];
  submit: [name: string];
}>();

const value = ref(props.initialValue);
const localError = ref("");
const formId = `master-catalog-form-${useId()}`;

watch(
  () => props.open,
  (open) => {
    if (!open) return;
    value.value = props.initialValue;
    localError.value = "";
  },
);

function cancel(): void {
  if (props.busy) return;
  emit("close");
}

function submit(): void {
  if (props.busy) return;
  const name = value.value.trim();
  if (!name) {
    localError.value = "Informe o nome.";
    return;
  }
  localError.value = "";
  emit("submit", name);
}
</script>

<template>
  <AppModal :open="props.open" :title="props.title" :busy="props.busy" @close="cancel">
    <form :id="formId" class="modal-form" @submit.prevent="submit">
      <label class="field">
        <span>{{ props.label }} *</span>
        <input
          v-model="value"
          :maxlength="props.maxLength"
          :placeholder="props.placeholder"
          :disabled="props.busy"
          required
          autocomplete="off"
          @input="localError = ''"
        />
      </label>
      <p v-if="props.hint" class="modal-hint">
        <Info :size="14" aria-hidden="true" />
        <span>{{ props.hint }}</span>
      </p>
      <p v-if="props.error || localError" class="inline-error" role="alert">
        {{ props.error || localError }}
      </p>
    </form>

    <template #actions>
      <Button variant="outline" size="sm" :disabled="props.busy" @click="cancel">
        <X aria-hidden="true" /> Cancelar
      </Button>
      <Button
        type="submit"
        size="sm"
        :form="formId"
        :disabled="props.busy"
        :loading="props.busy"
      >
        <Check v-if="!props.busy" aria-hidden="true" />
        {{ props.busy ? "Salvando..." : props.confirmLabel }}
      </Button>
    </template>
  </AppModal>
</template>

<style scoped>
.modal-form {
  display: grid;
  gap: 14px;
}

.modal-hint {
  display: flex;
  align-items: flex-start;
  gap: 7px;
  margin: 0;
  border-radius: 9px;
  padding: 9px 10px;
  background: #f2f7fd;
  color: #436485;
  font-size: 11.5px;
  line-height: 1.5;
}

.modal-hint svg {
  flex: 0 0 auto;
  margin-top: 1px;
}

.inline-error {
  margin: 0;
  color: #a4453a;
  font-size: 11.5px;
  font-weight: 700;
  line-height: 1.45;
}
</style>
