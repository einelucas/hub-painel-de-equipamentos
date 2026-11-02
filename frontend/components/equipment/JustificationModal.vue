<script setup lang="ts">
import { ref, watch } from "vue";
import { VBtn, VTextarea } from "vuetify/components";

const props = defineProps<{
  open: boolean;
  title: string;
  message?: string;
  required?: boolean;
  confirmLabel?: string;
  confirmColor?: "primary" | "success" | "warning" | "error";
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
      <VTextarea
        v-model="text"
        :label="`Justificativa${required ? ' *' : ''}`"
        maxlength="1000"
        :counter="1000"
        :required="required"
        :disabled="busy"
        rows="3"
      />
      <VAlert v-if="error" type="error" role="alert">{{ error }}</VAlert>
      <div class="form-actions">
        <VBtn variant="outlined" @click="emit('close')">Cancelar</VBtn>
        <VBtn
          type="submit"
          variant="tonal"
          :color="confirmColor ?? 'primary'"
          :loading="busy"
          :disabled="required && !text.trim()"
        >
          {{ busy ? "Processando..." : (confirmLabel ?? "Confirmar") }}
        </VBtn>
      </div>
    </form>
  </AppModal>
</template>

<style scoped>
.justification-form { display: grid; gap: 14px; }
.justification-message { margin: 0; color: #65748a; font-size: 12px; }
.form-actions { display: flex; justify-content: flex-end; gap: 9px; }
</style>
