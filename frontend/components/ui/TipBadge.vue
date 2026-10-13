<script setup lang="ts">
withDefaults(defineProps<{ label: string; tip: string; tone?: "blue" | "neutral" | "muted" }>(), {
  tone: "blue",
});
</script>

<template>
  <span class="tip-badge" :class="`tip-badge--${tone}`" tabindex="0">
    <span class="tip-badge-label">{{ label }}</span>
    <!-- Mesmo balão da navegação (TabsNav), aberto acima para não ser recortado pelo scroll da tabela. -->
    <span class="tip-badge-tip" role="tooltip">{{ tip }}</span>
  </span>
</template>

<style scoped>
.tip-badge { position: relative; display: inline-flex; white-space: nowrap; border-radius: 999px; padding: 4px 8px; font-size: 11px; font-weight: 750; cursor: default; }
.tip-badge:focus-visible { outline: 2px solid #304f7e; outline-offset: 2px; }
.tip-badge--blue { background: #e8f1fc; color: #2f5f9c; }
.tip-badge--neutral { background: #eef2f7; color: #2b3e58; }
.tip-badge--muted { background: #e1e7ef; color: #56657c; }

.tip-badge-tip {
  position: absolute;
  bottom: calc(100% + 9px);
  left: 50%;
  z-index: 30;
  border-radius: 9px;
  padding: 5px 10px;
  background: #2b3e58;
  color: #fff;
  font-size: 11.5px;
  font-weight: 700;
  white-space: pre;
  opacity: 0;
  pointer-events: none;
  transform: translate(-50%, 3px);
  transition: opacity .14s ease, transform .14s ease;
}
.tip-badge-tip::before {
  position: absolute;
  top: 100%;
  left: 50%;
  border: 5px solid transparent;
  border-top-color: #2b3e58;
  content: "";
  transform: translateX(-50%);
}
.tip-badge:hover .tip-badge-tip,
.tip-badge:focus-visible .tip-badge-tip {
  opacity: 1;
  transform: translate(-50%, 0);
}
@media (prefers-reduced-motion: reduce) {
  .tip-badge-tip { transition: none; }
}
</style>
