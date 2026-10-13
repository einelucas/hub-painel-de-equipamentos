<script setup lang="ts">
import { computed } from "vue";
import type { NamedRef } from "~/types/equipment";
import TipBadge from "~/components/ui/TipBadge.vue";

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
    <TipBadge
      v-for="item in visibleItems"
      :key="item.id"
      class="wp-chip"
      tone="neutral"
      :label="item.code ?? item.name"
      :tip="description(item)"
    />
    <TipBadge
      v-if="hiddenItems.length"
      class="wp-chip wp-chip--more"
      tone="muted"
      :label="`+${hiddenItems.length}`"
      :tip="hiddenDescription"
    />
  </div>
</template>

<style scoped>
/* Compacto: no máx. 3 chips + "+N", nunca aumenta a altura da linha. */
.wp-chips { display: flex; flex-wrap: wrap; gap: 4px; max-width: 220px; }
.wp-chips .wp-chip { padding: 3px 8px; font-size: 10.5px; font-weight: 700; }
</style>
