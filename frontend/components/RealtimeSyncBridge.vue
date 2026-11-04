<script setup lang="ts">
import type { RealtimeChangeEvent } from "~/composables/useRealtimeSync";
const sync = useRealtimeSync();
const context = useModuleContextStore();
let unsubscribe: (() => void) | null = null;

async function refreshContext(event: RealtimeChangeEvent): Promise<void> {
  if (!context.loaded) return;
  if (event.eventType === "revalidate" || event.entityType === "project_context") {
    await context.loadProjectContexts();
    await context.loadEquipmentOptions();
    return;
  }
  if (
    event.entityType === "equipment" &&
    (!context.selectedUnit || event.unitId === context.selectedUnit)
  ) {
    await context.loadEquipmentOptions();
  }
}

function onVisibility(): void {
  if (document.visibilityState === "visible") sync.revalidate();
}

onMounted(() => {
  sync.start();
  unsubscribe = sync.subscribe(refreshContext);
  document.addEventListener("visibilitychange", onVisibility);
  window.addEventListener("online", sync.revalidate);
});
onBeforeUnmount(() => {
  unsubscribe?.();
  document.removeEventListener("visibilitychange", onVisibility);
  window.removeEventListener("online", sync.revalidate);
  sync.stop();
});
</script>

<template><span class="sr-only" aria-live="polite" /></template>
