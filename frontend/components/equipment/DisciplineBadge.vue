<script setup lang="ts">
import { computed } from "vue";
import type { NamedRef } from "~/types/equipment";
import { disciplineColor, translucentBadgeStyle } from "~/utils/catalogColors";
import { useAnchoredTip } from "~/composables/useAnchoredTip";

const props = withDefaults(defineProps<{ discipline: NamedRef; focusable?: boolean }>(), {
  focusable: true,
});
const style = computed(() => translucentBadgeStyle(disciplineColor(props.discipline)));

const { trigger, tip: tipEl, open, above, style: tipStyle, show, hide } = useAnchoredTip();
</script>

<template>
  <span
    ref="trigger"
    class="catalog-badge discipline-badge"
    :style="style"
    :tabindex="focusable ? 0 : undefined"
    data-testid="discipline-badge"
    @mouseenter="show"
    @mouseleave="hide"
    @focus="show"
    @blur="hide"
  >
    <span class="catalog-badge-label tip-badge-label">{{ discipline.code ?? discipline.name }}</span>
    <!-- Balão preso à viewport: `absolute` era recortado pelo overflow da tabela. -->
    <span
      ref="tipEl"
      class="catalog-badge-tip"
      :class="{ 'catalog-badge-tip--open': open, 'catalog-badge-tip--below': !above }"
      :style="tipStyle"
      role="tooltip"
    >{{ discipline.name }}</span>
  </span>
</template>

<style scoped>
.catalog-badge { position: relative; display: inline-flex; width: 64px; height: 26px; align-items: center; justify-content: center; box-sizing: border-box; border: 1px solid var(--badge-border); border-radius: 999px; background: var(--badge-background); color: #263b59; cursor: default; font-size: 11px; font-weight: 800; line-height: 1; white-space: nowrap; }
.catalog-badge:focus-visible { outline: 2px solid var(--badge-color); outline-offset: 2px; }
.catalog-badge-label { max-width: 48px; overflow: hidden; text-overflow: ellipsis; }
.catalog-badge-tip { position: fixed; z-index: 60; width: max-content; border-radius: 9px; padding: 5px 10px; background: #2b3e58; color: #fff; font-size: 11.5px; font-weight: 700; white-space: nowrap; opacity: 0; pointer-events: none; transition: opacity .14s ease; }
.catalog-badge-tip--open { opacity: 1; }
.catalog-badge-tip::before { position: absolute; top: 100%; left: var(--tip-arrow, 50%); border: 5px solid transparent; border-top-color: #2b3e58; content: ""; transform: translateX(-50%); }
.catalog-badge-tip--below::before { top: auto; bottom: 100%; border-top-color: transparent; border-bottom-color: #2b3e58; }
@media (prefers-reduced-motion: reduce) { .catalog-badge-tip { transition: none; } }
</style>
