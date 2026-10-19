<script setup lang="ts">
import { computed } from "vue";
import { useAnchoredTip } from "~/composables/useAnchoredTip";

const props = withDefaults(
  defineProps<{
    /** Texto completo (exibido inteiro dentro do balão). */
    text: string;
    /**
     * Limite de caracteres antes de truncar com "…".
     * Altere aqui para padronizar a largura das colunas que usam este componente.
     */
    max?: number;
  }>(),
  { max: 40 },
);

const truncated = computed(() => props.text.length > props.max);
const display = computed(() =>
  truncated.value ? `${props.text.slice(0, props.max).trimEnd()}…` : props.text,
);

const { trigger, tip: tipEl, open, above, style: tipStyle, show, hide } = useAnchoredTip();

function showTip(): void {
  if (truncated.value) show();
}
</script>

<template>
  <span
    ref="trigger"
    class="truncated-text"
    :tabindex="truncated ? 0 : undefined"
    @mouseenter="showTip"
    @mouseleave="hide"
    @focus="showTip"
    @blur="hide"
  >
    <span class="truncated-text-label">{{ display }}</span>
    <!-- Mesmo balão do badge de disciplina (DisciplineBadge), preso à viewport
         para não ser recortado pelo overflow da tabela. -->
    <span
      v-if="truncated"
      ref="tipEl"
      class="truncated-text-tip"
      :class="{ 'truncated-text-tip--open': open, 'truncated-text-tip--below': !above }"
      :style="tipStyle"
      role="tooltip"
    >{{ text }}</span>
  </span>
</template>

<style scoped>
.truncated-text { position: relative; display: inline-block; max-width: 100%; }
.truncated-text-label { display: inline-block; overflow: hidden; vertical-align: bottom; text-overflow: ellipsis; white-space: nowrap; }
.truncated-text:focus-visible { border-radius: 4px; outline: 2px solid #304f7e; outline-offset: 2px; }
.truncated-text-tip {
  position: fixed;
  z-index: 60;
  width: max-content;
  max-width: min(420px, calc(100vw - 16px));
  border-radius: 9px;
  padding: 5px 10px;
  background: #2b3e58;
  color: #fff;
  font-size: 11.5px;
  font-weight: 700;
  line-height: 1.45;
  white-space: pre-wrap;
  opacity: 0;
  pointer-events: none;
  transition: opacity .14s ease;
}
.truncated-text-tip--open { opacity: 1; }
.truncated-text-tip::before {
  position: absolute;
  top: 100%;
  left: var(--tip-arrow, 50%);
  border: 5px solid transparent;
  border-top-color: #2b3e58;
  content: "";
  transform: translateX(-50%);
}
.truncated-text-tip--below::before {
  top: auto;
  bottom: 100%;
  border-top-color: transparent;
  border-bottom-color: #2b3e58;
}
@media (prefers-reduced-motion: reduce) {
  .truncated-text-tip { transition: none; }
}
</style>
