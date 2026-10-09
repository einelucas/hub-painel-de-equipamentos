<script setup lang="ts">
import { computed } from "vue";
import type { NamedRef } from "~/types/equipment";

const props = withDefaults(defineProps<{ items: NamedRef[]; maxVisible?: number }>(), {
  maxVisible: 3,
});

const visibleItems = computed(() => props.items.slice(0, props.maxVisible));
const hiddenItems = computed(() => props.items.slice(props.maxVisible));
const description = (item: NamedRef): string => item.description?.trim() || "WP sem descrição";
const hiddenDescription = computed(() =>
  hiddenItems.value
    .map((item) => `${item.code ?? item.name}: ${description(item)}`)
    .join("\n"),
);
</script>

<template>
  <span v-if="items.length === 0">—</span>
  <div v-else class="wp-chips">
    <span
      v-for="item in visibleItems"
      :key="item.id"
      class="wp-chip"
      :title="description(item)"
      tabindex="0"
    >{{ item.code ?? item.name }}</span>
    <span
      v-if="hiddenItems.length"
      class="wp-chip wp-chip--more"
      :title="hiddenDescription"
      tabindex="0"
    >+{{ hiddenItems.length }}</span>
  </div>
</template>

<style scoped>
/* Compacto: no máx. 3 chips + "+N", nunca aumenta a altura da linha. */
.wp-chips { display: flex; flex-wrap: wrap; gap: 4px; max-width: 220px; }
.wp-chip { display: inline-flex; white-space: nowrap; border-radius: 999px; padding: 3px 8px; font-size: 10.5px; font-weight: 700; background: #eef2f7; color: #2b3e58; }
.wp-chip--more { background: #e1e7ef; color: #56657c; }
</style>
