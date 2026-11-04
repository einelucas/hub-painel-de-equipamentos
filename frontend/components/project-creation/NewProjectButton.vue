<script setup lang="ts">
import { mdiFolderPlusOutline } from "@mdi/js";
import { VBtn, VIcon } from "vuetify/components";
import { computed } from "vue";
import NewProjectModal from "~/components/project-creation/NewProjectModal.vue";
import { useProjectCreation } from "~/composables/useProjectCreation";

const auth = useAuthStore();
const context = useModuleContextStore();
const canCreate = computed(() => auth.can("catalogs:manage") && auth.can("equipments:write"));
const creation = useProjectCreation();

async function created(): Promise<void> {
  creation.notifyCreated();
  await Promise.all([context.loadProjectContexts(), context.loadEquipmentOptions()]);
}
</script>

<template>
  <template v-if="canCreate">
    <VBtn
      type="button"
      class="module-action"
      variant="text"
      aria-label="Nova obra"
      data-testid="nav-new-project"
      :icon="mdiFolderPlusOutline"
      @click="creation.openNewProject(context.selectedUnit)"
    >
      <VIcon :icon="mdiFolderPlusOutline" size="18" aria-hidden="true" />
      <span class="module-nav-tip" aria-hidden="true">Nova obra</span>
    </VBtn>
    <NewProjectModal
      :open="creation.open.value"
      :initial-unit-id="creation.initialUnitId.value || context.selectedUnit"
      @close="creation.closeNewProject"
      @created="created"
    />
  </template>
</template>
