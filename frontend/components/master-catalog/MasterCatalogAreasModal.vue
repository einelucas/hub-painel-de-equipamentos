<script setup lang="ts">
import { mdiDotsVertical, mdiMagnify, mdiPencilOutline, mdiPlus, mdiPower, mdiTrashCanOutline } from "@mdi/js";
import { computed, ref } from "vue";
import { VBtn, VList, VListItem, VMenu, VTextField } from "vuetify/components";
import AppModal from "~/components/ui/AppModal.vue";
import Badge from "~/components/ui/Badge.vue";
import type { MasterArea, MasterEquipment } from "~/types/masterCatalog";
import { areaUsage } from "~/utils/masterCatalog";
import { matchesSearchText } from "~/utils/search";

const props = defineProps<{
  open: boolean;
  areas: MasterArea[];
  equipments: MasterEquipment[];
  busy: boolean;
  deletingId: string;
  error: string;
}>();
const newAreaName = defineModel<string>("newAreaName", { required: true });
const emit = defineEmits<{
  close: [];
  add: [name: string];
  rename: [area: MasterArea];
  toggle: [area: MasterArea];
  remove: [area: MasterArea];
}>();
const search = ref("");
const managedAreas = computed(() =>
  [...props.areas]
    .filter((area) => matchesSearchText(area.name, search.value.trim()))
    .sort((left, right) => {
      if (left.isUnassigned !== right.isUnassigned) return left.isUnassigned ? -1 : 1;
      if (left.active !== right.active) return left.active ? -1 : 1;
      return left.name.localeCompare(right.name, "pt-BR");
    }),
);
const activeCount = computed(() => props.areas.filter((area) => area.active && !area.isUnassigned).length);
function addArea(): void {
  const name = newAreaName.value.trim();
  if (!name || props.busy) return;
  emit("add", name);
}
function isDeleting(area: MasterArea): boolean {
  return props.deletingId === `/master-catalog/areas/${area.id}`;
}
</script>

<template>
  <AppModal :open="props.open" title="Gerenciar áreas do catálogo" :busy="props.busy" @close="emit('close')">
    <div class="areas-modal">
      <p class="areas-intro">
        Uma área pode estar vinculada a diversos equipamentos. Cadastre as áreas aqui e
        associe-as aos modelos na tela principal.
      </p>
      <form class="create-area" @submit.prevent="addArea">
        <VTextField
          v-model="newAreaName"
          label="Nova área"
          placeholder="Informe o nome da área"
          maxlength="160"
          autocomplete="off"
          :disabled="props.busy"
        />
        <VBtn
          type="submit"
          variant="flat"
          color="primary"
          :prepend-icon="mdiPlus"
          :disabled="props.busy || !newAreaName.trim()"
        >Adicionar</VBtn>
      </form>
      <VAlert v-if="props.error" type="error" role="alert">{{ props.error }}</VAlert>

      <div class="area-list-header">
        <div><h3>Áreas cadastradas</h3><span>{{ activeCount }} ativas · {{ props.areas.length }} registros</span></div>
        <VTextField
          v-model="search"
          class="area-search"
          label="Buscar área"
          :prepend-inner-icon="mdiMagnify"
          clearable
          autocomplete="off"
        />
      </div>
      <ul class="areas-list">
        <li v-for="area in managedAreas" :key="area.id" class="area-row">
          <div class="area-row__main">
            <div class="area-row__name"><strong>{{ area.name }}</strong><Badge v-if="area.isUnassigned" variant="outline">Padrão do sistema</Badge></div>
            <p>{{ areaUsage(area, props.equipments) }}</p>
          </div>
          <Badge :variant="area.active ? 'success' : 'secondary'">{{ area.active ? 'Ativa' : 'Inativa' }}</Badge>
          <VMenu v-if="!area.isUnassigned">
            <template #activator="{ props: menuProps }">
              <VBtn
                v-bind="menuProps"
                size="small"
                variant="text"
                :icon="mdiDotsVertical"
                :loading="isDeleting(area)"
                :disabled="props.busy"
                :aria-label="`Ações para área ${area.name}`"
              />
            </template>
            <VList density="compact" min-width="180" class="action-menu">
              <VListItem :prepend-icon="mdiPencilOutline" title="Renomear" @click="emit('rename', area)" />
              <VListItem :prepend-icon="mdiPower" :title="area.active ? 'Desativar' : 'Reativar'" @click="emit('toggle', area)" />
              <VListItem :prepend-icon="mdiTrashCanOutline" title="Excluir" class="delete-item" @click="emit('remove', area)" />
            </VList>
          </VMenu>
          <span v-else class="protected-status">Protegida</span>
        </li>
        <li v-if="!managedAreas.length" class="no-areas">Nenhuma área encontrada. Ajuste a busca.</li>
      </ul>
      <p class="modal-note">
        “Sem área definida” é uma categoria protegida. Desativar ou excluir uma área do
        catálogo não modifica equipamentos já criados nas obras.
      </p>
    </div>
    <template #actions>
      <VBtn variant="outlined" size="small" :disabled="props.busy" @click="emit('close')">Fechar</VBtn>
    </template>
  </AppModal>
</template>

<style scoped>
.areas-modal { display: grid; gap: 16px; }
.areas-intro { margin: 0; color: #65788f; font-size: 12px; line-height: 1.55; }
.create-area { display: flex; align-items: flex-start; gap: 9px; }
.create-area > :first-child { min-width: 0; flex: 1; }
.create-area > :last-child { margin-top: 3px; }
.area-list-header { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 12px; border-top: 1px solid #e8edf3; padding-top: 16px; }
.area-list-header h3 { margin: 0 0 4px; color: #263e59; font-size: 13px; }
.area-list-header span { color: #8a97a8; font-size: 11px; }
.area-search { max-width: 260px; }
.areas-list { display: grid; gap: 6px; max-height: 330px; margin: 0; padding: 0 3px 0 0; overflow-y: auto; list-style: none; scrollbar-width: thin; }
.area-row { display: flex; align-items: center; gap: 10px; border: 1px solid #e7edf4; border-radius: 10px; padding: 11px 12px; }
.area-row__main { min-width: 0; flex: 1; }
.area-row__name { display: flex; min-width: 0; flex-wrap: wrap; align-items: center; gap: 7px; }
.area-row__name strong { overflow-wrap: anywhere; color: #344b66; font-size: 12px; }
.area-row__main p { margin: 5px 0 0; color: #8998a9; font-size: 10.5px; line-height: 1.5; }
.protected-status { color: #91a0b0; font-size: 11px; }
.no-areas { padding: 30px 10px; color: #8091a4; font-size: 12px; text-align: center; }
.modal-note { margin: 0; color: #8695a7; font-size: 10.5px; line-height: 1.55; }
.action-menu { padding: 5px; border: 1px solid #e4eaf2; border-radius: 11px; }
:deep(.delete-item .v-list-item-title) { color: #ba4945; }
@media (max-width: 550px) { .create-area { flex-direction: column; } .create-area > :first-child, .create-area > :last-child, .area-search { width: 100%; max-width: 100%; } .area-row { gap: 6px; padding: 9px; } }
</style>
