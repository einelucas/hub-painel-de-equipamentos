<script setup lang="ts">
import { computed } from "vue";

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
</script>

<template>
  <span class="truncated-text" :tabindex="truncated ? 0 : undefined">
    <span class="truncated-text-label">{{ display }}</span>
    <!-- Mesmo balão do badge de disciplina (DisciplineBadge), aberto acima para não ser recortado pela tabela. -->
    <span v-if="truncated" class="truncated-text-tip" role="tooltip">{{ text }}</span>
  </span>
</template>

<style scoped>
.truncated-text { position: relative; display: inline-block; max-width: 100%; }
.truncated-text-label { display: inline-block; overflow: hidden; vertical-align: bottom; text-overflow: ellipsis; white-space: nowrap; }
.truncated-text:focus-visible { border-radius: 4px; outline: 2px solid #304f7e; outline-offset: 2px; }
.truncated-text-tip {
  position: absolute;
  bottom: calc(100% + 9px);
  left: 0;
  z-index: 30;
  border-radius: 9px;
  padding: 5px 10px;
  background: #2b3e58;
  color: #fff;
  font-size: 11.5px;
  font-weight: 700;
  white-space: nowrap;
  opacity: 0;
  pointer-events: none;
  transform: translateY(3px);
  transition: opacity .14s ease, transform .14s ease;
}
.truncated-text-tip::before {
  position: absolute;
  top: 100%;
  left: 12px;
  border: 5px solid transparent;
  border-top-color: #2b3e58;
  content: "";
  transform: translateX(-50%);
}
.truncated-text:hover .truncated-text-tip,
.truncated-text:focus-visible .truncated-text-tip {
  opacity: 1;
  transform: translateY(0);
}
@media (prefers-reduced-motion: reduce) {
  .truncated-text-tip { transition: none; }
}
</style>
