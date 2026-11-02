<script setup lang="ts">
import { mdiFolderPlusOutline } from "@mdi/js";
import { VBtn, VIcon } from "vuetify/components";
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
      class="module-action"
      variant="text"
      aria-label="Nova obra"
      data-testid="nav-new-project"
      :icon="mdiFolderPlusOutline"
      @click="open = true"
    >
      <VIcon :icon="mdiFolderPlusOutline" size="18" aria-hidden="true" />
      <span class="module-nav-tip" aria-hidden="true">Nova obra</span>
    </VBtn>
    <NewProjectModal :open="open" :initial-unit-id="context.selectedUnit" @close="open = false" />
  </template>
</template>
