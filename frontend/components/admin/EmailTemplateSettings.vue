<script setup lang="ts">
import { LayoutTemplate } from "lucide-vue-next";

type VisualOptions = {
  showDetails: boolean;
  showAlert: boolean;
  showButton: boolean;
  showFooter: boolean;
};

const props = defineProps<{ modelValue: VisualOptions; disabled?: boolean }>();
const emit = defineEmits<{ "update:modelValue": [value: VisualOptions] }>();

const options: { key: keyof VisualOptions; label: string; hint: string }[] = [
  { key: "showAlert", label: "Destaque do alerta", hint: "Faixa com o tipo de evento e a criticidade" },
  { key: "showDetails", label: "Dados do equipamento", hint: "Cartão com TAG, unidade, obra, responsável e prazos" },
  { key: "showButton", label: "Botão de ação", hint: "Ocultado quando não existe URL válida" },
  { key: "showFooter", label: "Rodapé institucional", hint: "Aviso de geração automática" },
];

function toggle(key: keyof VisualOptions): void {
  if (props.disabled) return;
  emit("update:modelValue", { ...props.modelValue, [key]: !props.modelValue[key] });
}
</script>

<template>
  <section class="tpl-settings">
    <header><LayoutTemplate :size="14" /><strong>Elementos visuais</strong></header>
    <label v-for="option in options" :key="option.key" class="tpl-setting">
      <input
        type="checkbox"
        :checked="modelValue[option.key]"
        :disabled="disabled"
        @change="toggle(option.key)"
      />
      <span>
        <strong>{{ option.label }}</strong>
        <small>{{ option.hint }}</small>
      </span>
    </label>
  </section>
</template>

<style scoped>
.tpl-settings { display: grid; gap: 8px; border: 1px solid #e2e8f0; border-radius: 10px; padding: 12px; }
.tpl-settings header { display: flex; gap: 6px; align-items: center; font-size: 12px; color: #24364f; }
.tpl-setting { display: flex; gap: 9px; align-items: start; font-size: 12px; color: #24364f; }
.tpl-setting input { margin-top: 2px; accent-color: #304f7e; }
.tpl-setting span { display: grid; gap: 1px; }
.tpl-setting strong { font-size: 12px; font-weight: 650; }
.tpl-setting small { color: #64748b; font-size: 11px; line-height: 1.4; }
</style>
