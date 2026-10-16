<script setup lang="ts">
import { computed } from "vue";
import type { NamedRef } from "~/types/equipment";
import { disciplineColor, translucentBadgeStyle } from "~/utils/catalogColors";

const props = withDefaults(defineProps<{ discipline: NamedRef; focusable?: boolean }>(), {
  focusable: true,
});
const style = computed(() => translucentBadgeStyle(disciplineColor(props.discipline)));
</script>

<template>
  <span class="catalog-badge discipline-badge" :style="style" :tabindex="focusable ? 0 : undefined" data-testid="discipline-badge">
    <span class="catalog-badge-label tip-badge-label">{{ discipline.code ?? discipline.name }}</span>
    <span class="catalog-badge-tip tip-badge-tip" role="tooltip">{{ discipline.name }}</span>
  </span>
</template>

<style scoped>
.catalog-badge { position: relative; display: inline-flex; width: 64px; height: 26px; align-items: center; justify-content: center; box-sizing: border-box; border: 1px solid var(--badge-border); border-radius: 999px; background: var(--badge-background); color: #263b59; cursor: default; font-size: 11px; font-weight: 800; line-height: 1; white-space: nowrap; }
.catalog-badge:focus-visible { outline: 2px solid var(--badge-color); outline-offset: 2px; }
.catalog-badge-label { max-width: 48px; overflow: hidden; text-overflow: ellipsis; }
.catalog-badge-tip { position: absolute; bottom: calc(100% + 9px); left: 50%; z-index: 30; border-radius: 9px; padding: 5px 10px; background: #2b3e58; color: #fff; font-size: 11.5px; font-weight: 700; white-space: nowrap; opacity: 0; pointer-events: none; transform: translate(-50%, 3px); transition: opacity .14s ease, transform .14s ease; }
.catalog-badge-tip::before { position: absolute; top: 100%; left: 50%; border: 5px solid transparent; border-top-color: #2b3e58; content: ""; transform: translateX(-50%); }
.catalog-badge:hover .catalog-badge-tip, .catalog-badge:focus-visible .catalog-badge-tip { opacity: 1; transform: translate(-50%, 0); }
@media (prefers-reduced-motion: reduce) { .catalog-badge-tip { transition: none; } }
</style>
