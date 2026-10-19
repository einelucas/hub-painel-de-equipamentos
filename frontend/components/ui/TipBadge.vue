<script setup lang="ts">
import { useAnchoredTip } from "~/composables/useAnchoredTip";

withDefaults(defineProps<{ label: string; tip: string; tone?: "blue" | "neutral" | "muted" }>(), {
  tone: "blue",
});

const { trigger, tip: tipEl, open, above, style: tipStyle, show, hide } = useAnchoredTip();
</script>

<template>
  <span
    ref="trigger"
    class="tip-badge"
    :class="`tip-badge--${tone}`"
    tabindex="0"
    @mouseenter="show"
    @mouseleave="hide"
    @focus="show"
    @blur="hide"
  >
    <span class="tip-badge-label">{{ label }}</span>
    <!-- Mesmo balão da navegação (TabsNav), preso à viewport para não ser
         recortado pelo overflow/scroll da tabela que hospeda o badge. -->
    <span
      ref="tipEl"
      class="tip-badge-tip"
      :class="{ 'tip-badge-tip--open': open, 'tip-badge-tip--below': !above }"
      :style="tipStyle"
      role="tooltip"
    >{{ tip }}</span>
  </span>
</template>

<style scoped>
.tip-badge { position: relative; display: inline-flex; white-space: nowrap; border-radius: 999px; padding: 4px 8px; font-size: 11px; font-weight: 750; cursor: default; }
.tip-badge:focus-visible { outline: 2px solid #304f7e; outline-offset: 2px; }
.tip-badge--blue { background: #e8f1fc; color: #2f5f9c; }
.tip-badge--neutral { background: #eef2f7; color: #2b3e58; }
.tip-badge--muted { background: #e1e7ef; color: #56657c; }

.tip-badge-tip {
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
.tip-badge-tip--open { opacity: 1; }
.tip-badge-tip::before {
  position: absolute;
  top: 100%;
  left: var(--tip-arrow, 50%);
  border: 5px solid transparent;
  border-top-color: #2b3e58;
  content: "";
  transform: translateX(-50%);
}
.tip-badge-tip--below::before {
  top: auto;
  bottom: 100%;
  border-top-color: transparent;
  border-bottom-color: #2b3e58;
}
@media (prefers-reduced-motion: reduce) {
  .tip-badge-tip { transition: none; }
}
</style>
