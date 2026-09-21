<script setup lang="ts">
import type { PendingRequirement } from "~/types/equipment";

defineProps<{
  pending: PendingRequirement[];
  nextStageName: string | null;
}>();
</script>

<template>
  <div class="pending">
    <div v-if="!nextStageName" class="pending-status pending-status--done">
      <span class="status-dot" />
      <span>Processo concluído</span>
    </div>

    <div
      v-else-if="pending.length === 0"
      class="pending-status pending-status--ready"
    >
      <span class="status-dot" />
      <span>Pronto para {{ nextStageName }}</span>
    </div>

    <template v-else>
      <div class="pending-header">
        <div class="pending-heading">
          <span class="pending-label">Falta para avançar</span>

          <strong class="pending-stage">
            {{ nextStageName }}
          </strong>
        </div>
      </div>

      <ul class="pending-list">
        <li v-for="item in pending" :key="item.code" class="pending-item">
          <span class="pending-bullet" />

          <span class="pending-message">
            {{ item.message }}
          </span>
        </li>
      </ul>
    </template>
  </div>
</template>

<style scoped>
.pending {
  display: flex;
  width: 100%;
  min-width: 220px;
  max-width: 300px;
  flex-direction: column;
  gap: 8px;
  box-sizing: border-box;
}

.pending-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.pending-heading {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
  gap: 2px;
}

.pending-label {
  color: #8b96a5;
  font-size: 9.5px;
  font-weight: 700;
  line-height: 1.2;
  letter-spacing: 0.045em;
  text-transform: uppercase;
}

.pending-stage {
  color: #59677c;
  font-size: 11.5px;
  font-weight: 700;
  line-height: 1.3;
  overflow-wrap: normal;
  word-break: normal;
}

.pending-list {
  display: flex;
  flex-direction: column;
  gap: 5px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.pending-item {
  display: flex;
  min-width: 0;
  align-items: flex-start;
  gap: 7px;
  padding: 6px 8px;
  border: 1px solid #eee4d3;
  border-radius: 6px;
  background: #fffbf4;
}

.pending-bullet {
  width: 5px;
  height: 5px;
  flex: 0 0 5px;
  margin-top: 5px;
  border-radius: 50%;
  background: #c28a3d;
}

.pending-message {
  min-width: 0;
  color: #855d25;
  font-size: 10.5px;
  font-weight: 500;
  line-height: 1.4;
  overflow-wrap: break-word;
  word-break: normal;
  white-space: normal;
}

.pending-status {
  display: inline-flex;
  width: fit-content;
  max-width: 100%;
  align-items: center;
  gap: 7px;
  padding: 6px 9px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 700;
  line-height: 1.3;
}

.status-dot {
  width: 6px;
  height: 6px;
  flex: 0 0 6px;
  border-radius: 50%;
}

.pending-status--done {
  border: 1px solid #d8e8cf;
  background: #f4faef;
  color: #477a32;
}

.pending-status--done .status-dot {
  background: #5e913f;
}

.pending-status--ready {
  border: 1px solid #d5e2f3;
  background: #f3f7fc;
  color: #2f5f9c;
}

.pending-status--ready .status-dot {
  background: #4278b8;
}
</style>
