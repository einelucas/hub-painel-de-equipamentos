<script setup lang="ts">
import type { PendingRequirement } from "~/types/equipment";

defineProps<{ pending: PendingRequirement[]; nextStageName: string | null }>();
</script>

<template>
  <div class="pending">
    <span v-if="!nextStageName" class="pending-done">Processo concluído</span>
    <template v-else-if="pending.length === 0">
      <span class="pending-ready">Pronto para {{ nextStageName }}</span>
    </template>
    <template v-else>
      <span class="pending-label">Falta para {{ nextStageName }}:</span>
      <ul>
        <li v-for="item in pending" :key="item.code">{{ item.message }}</li>
      </ul>
    </template>
  </div>
</template>

<style scoped>
.pending { display: grid; gap: 3px; }
.pending-done { color: #477a32; font-size: 11.5px; font-weight: 700; }
.pending-ready { color: #2f5f9c; font-size: 11.5px; font-weight: 700; }
.pending-label { color: #8b96a5; font-size: 10px; font-weight: 800; letter-spacing: .04em; text-transform: uppercase; }
.pending ul { margin: 0; padding-left: 15px; color: #9b6418; font-size: 11.5px; }
</style>
