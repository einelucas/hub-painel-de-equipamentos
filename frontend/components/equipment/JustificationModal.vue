<script setup lang="ts">
import { ref, watch } from "vue";

const props = defineProps<{
  open: boolean;
  title: string;
  message?: string;
  required?: boolean;
  confirmLabel?: string;
  busy?: boolean;
  error?: string;
}>();
const emit = defineEmits<{ confirm: [text: string]; close: [] }>();

const text = ref("");

watch(
  () => props.open,
  (open) => {
    if (open) text.value = "";
  },
);

function submit(): void {
  if (props.required && !text.value.trim()) return;
  emit("confirm", text.value.trim());
}
</script>

<template>
  <AppModal :open="open" :title="title" @close="emit('close')">
    <form class="justification-form" @submit.prevent="submit">
      <p v-if="message" class="justification-message">{{ message }}</p>
      <label class="field">
        <span>Justificativa{{ required ? " *" : "" }}</span>
        <textarea v-model="text" maxlength="1000" :required="required" rows="3" />
      </label>
      <p v-if="error" class="notice error" role="alert">{{ error }}</p>
      <div class="form-actions">
        <button type="button" class="btn" @click="emit('close')">Cancelar</button>
        <button type="submit" class="btn primary" :disabled="busy || (required && !text.trim())">
          {{ busy ? "Processando..." : (confirmLabel ?? "Confirmar") }}
        </button>
      </div>
    </form>
  </AppModal>
</template>

<style scoped>
.justification-form { display: grid; gap: 14px; }
.justification-message { margin: 0; color: #65748a; font-size: 12px; }
.field { display: grid; gap: 4px; font-size: 12px; }
.field span { color: #7a879a; font-size: 10px; font-weight: 800; letter-spacing: .05em; text-transform: uppercase; }
.field textarea { border: 1px solid #d8dee7; border-radius: 6px; padding: 8px 9px; font-size: 13px; font-family: inherit; resize: vertical; }
.form-actions { display: flex; justify-content: flex-end; gap: 9px; }
</style>
