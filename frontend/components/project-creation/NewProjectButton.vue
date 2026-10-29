<script setup lang="ts">
import { mdiFolderPlusOutline } from "@mdi/js";
import { VBtn } from "vuetify/components";
import { computed, ref } from "vue";
import NewProjectModal from "~/components/project-creation/NewProjectModal.vue";

const auth = useAuthStore();
const context = useModuleContextStore();
const canCreate = computed(() => auth.can("catalogs:manage") && auth.can("equipments:write"));
const open = ref(false);
</script>

<template>
  <template v-if="canCreate">
    <VBtn
      type="button"
      variant="text"
      size="small"
      aria-label="Nova obra"
      title="Nova obra"
      data-testid="nav-new-project"
      :icon="mdiFolderPlusOutline"
      @click="open = true"
    />
    <NewProjectModal :open="open" :initial-unit-id="context.selectedUnit" @close="open = false" />
  </template>
</template>
