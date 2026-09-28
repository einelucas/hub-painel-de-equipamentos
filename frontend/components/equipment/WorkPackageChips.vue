<script setup lang="ts">
import type { NamedRef } from "~/types/equipment";

const MAX_VISIBLE = 3;
defineProps<{ items: NamedRef[] }>();
</script>

<template>
  <span v-if="items.length === 0">—</span>
  <div v-else class="wp-chips">
    <span v-for="item in items.slice(0, MAX_VISIBLE)" :key="item.id" class="wp-chip">{{ item.code ?? item.name }}</span>
    <span v-if="items.length > MAX_VISIBLE" class="wp-chip wp-chip--more">+{{ items.length - MAX_VISIBLE }}</span>
  </div>
</template>

<style scoped>
/* Compacto: no máx. 3 chips + "+N", nunca aumenta a altura da linha. */
.wp-chips { display: flex; flex-wrap: wrap; gap: 4px; max-width: 220px; }
.wp-chip { display: inline-flex; white-space: nowrap; border-radius: 999px; padding: 3px 8px; font-size: 10.5px; font-weight: 700; background: #eef2f7; color: #2b3e58; }
.wp-chip--more { background: #e1e7ef; color: #56657c; }
</style>
