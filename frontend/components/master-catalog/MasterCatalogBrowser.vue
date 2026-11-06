<script setup lang="ts">
import { mdiFilterOutline, mdiMagnify, mdiPackageVariantClosed } from "@mdi/js";
import { computed, ref } from "vue";
import { VAutocomplete, VBtn, VIcon, VList, VListItem, VTextField } from "vuetify/components";
import Badge from "~/components/ui/Badge.vue";
import NavigationMenu from "~/components/ui/NavigationMenu.vue";
import LoadingSpinner from "~/components/ui/LoadingSpinner.vue";
import type { MasterArea, MasterEquipment } from "~/types/masterCatalog";
import {
  activeRealAreas,
  areaSummary,
  buildAreaMap,
  filterEquipments,
  findUnassignedArea,
  plural,
} from "~/utils/masterCatalog";

const props = defineProps<{
  equipments: MasterEquipment[];
  areas: MasterArea[];
  selectedId: string;
  loading: boolean;
  busy: boolean;
  search: string;
  filterArea: string;
}>();

const emit = defineEmits<{
  "update:search": [value: string];
  "update:filterArea": [value: string];
  select: [equipment: MasterEquipment];
  clearFilters: [];
}>();

const statusFilter = ref<"all" | "active" | "inactive">("all");
const statusOptions = [
  { value: "all", label: "Todos" },
  { value: "active", label: "Ativos" },
  { value: "inactive", label: "Inativos" },
] as const;
const statusNavItems = statusOptions.map((option) => ({ value: option.value, label: option.label }));
const areaMap = computed(() => buildAreaMap(props.areas));
const realAreas = computed(() => activeRealAreas(props.areas));
const unassignedArea = computed(() => findUnassignedArea(props.areas));
const areaOptions = computed(() => [
  { title: "Todas as áreas", value: "" },
  { title: unassignedArea.value?.name ?? "Sem área definida", value: "unassigned" },
  ...realAreas.value.map((area) => ({ title: area.name, value: area.id })),
]);
const visibleEquipments = computed(() => {
  const matches = filterEquipments(props.equipments, props.areas, props.search, props.filterArea);
  return matches
    .filter((item) =>
      statusFilter.value === "all" || (statusFilter.value === "active" ? item.active : !item.active),
    )
    .sort((a, b) => Number(b.active) - Number(a.active) || a.name.localeCompare(b.name, "pt-BR"));
});
const hasFilters = computed(() =>
  Boolean(props.search.trim() || props.filterArea || statusFilter.value !== "all"),
);
const resultsLabel = computed(() =>
  `${visibleEquipments.value.length} de ${plural(props.equipments.length, "equipamento", "equipamentos")}`,
);

function updateSearch(value: unknown): void {
  emit("update:search", String(value ?? ""));
}
function updateArea(value: unknown): void {
  emit("update:filterArea", String(value ?? ""));
}
function resetFilters(): void {
  statusFilter.value = "all";
  emit("clearFilters");
}
</script>

<template>
  <aside class="surface master-browser" aria-label="Lista de equipamentos do catálogo">
    <div class="browser-heading">
      <div class="heading-number" aria-hidden="true">1</div>
      <div class="heading-copy">
        <h2>Escolha um equipamento</h2>
        <p>Selecione um modelo para configurar seus vínculos.</p>
      </div>
      <LoadingSpinner v-if="props.loading" size="sm" />
    </div>

    <div class="browser-tools">
      <VTextField
        :model-value="props.search"
        label="Buscar equipamentos"
        placeholder="Digite o nome do modelo"
        :prepend-inner-icon="mdiMagnify"
        clearable
        :disabled="props.loading && !props.equipments.length"
        autocomplete="off"
        aria-label="Buscar equipamentos por nome"
        @update:model-value="updateSearch"
        @click:clear="updateSearch('')"
      />
      <VAutocomplete
        :model-value="props.filterArea || null"
        :items="areaOptions"
        item-title="title"
        item-value="value"
        label="Filtrar por área"
        :prepend-inner-icon="mdiFilterOutline"
        clearable
        no-data-text="Nenhuma área encontrada"
        :disabled="props.loading && !props.equipments.length"
        @update:model-value="updateArea"
        @click:clear="updateArea('')"
      />
      <NavigationMenu
        v-model="statusFilter"
        :items="statusNavItems"
        :distributed="true"
        aria-label="Filtrar situação dos modelos"
      />
      <div class="result-row">
        <span aria-live="polite">{{ resultsLabel }}</span>
        <VBtn v-if="hasFilters" size="x-small" variant="text" @click="resetFilters">
          Limpar filtros
        </VBtn>
      </div>
    </div>

    <div class="browser-list" :aria-busy="props.loading">
      <div v-if="props.loading && !props.equipments.length" class="loading-list" role="status">
        <span v-for="index in 6" :key="index" class="list-skeleton" />
        <span class="sr-only">Carregando equipamentos...</span>
      </div>
      <div v-else-if="!props.equipments.length" class="browser-empty">
        <span class="empty-icon"><VIcon :icon="mdiPackageVariantClosed" size="26" /></span>
        <strong>Catálogo ainda vazio</strong>
        <p>Use “Novo equipamento” para cadastrar o primeiro modelo.</p>
      </div>
      <div v-else-if="!visibleEquipments.length" class="browser-empty">
        <strong>Nenhum equipamento encontrado</strong>
        <p>Tente outro termo ou remova os filtros aplicados.</p>
        <VBtn size="small" variant="outlined" @click="resetFilters">Limpar filtros</VBtn>
      </div>
      <VList v-else class="equipment-list" density="compact" bg-color="transparent" aria-label="Equipamentos encontrados">
        <VListItem
          v-for="item in visibleEquipments"
          :key="item.id"
          class="equipment-option"
          :class="{ 'equipment-option--selected': item.id === props.selectedId }"
          :active="item.id === props.selectedId"
          :aria-current="item.id === props.selectedId ? 'true' : undefined"
          :disabled="props.busy"
          color="primary"
          rounded="lg"
          @click="emit('select', item)"
        >
          <template #title><strong class="equipment-name" :title="item.name">{{ item.name }}</strong></template>
          <template #subtitle>
            <span class="equipment-option__meta">
              <span :title="areaSummary(item, areaMap)">{{ areaSummary(item, areaMap) }}</span>
              <span class="meta-dot" aria-hidden="true">·</span>
              <span>{{ item.components.length }} comp.</span>
            </span>
          </template>
          <template v-if="!item.active" #append><Badge variant="secondary">Inativo</Badge></template>
        </VListItem>
      </VList>
    </div>
    <p class="browser-footer">O equipamento selecionado pode estar associado a várias áreas.</p>
  </aside>
</template>

<style scoped>
.master-browser {
  position: sticky;
  top: 16px;
  display: flex;
  min-width: 0;
  height: 100%;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid #e5eaf1;
  border-radius: 15px;
  box-shadow: 0 5px 24px rgb(35 58 88 / 4%);
}
.browser-heading {
  display: flex;
  align-items: flex-start;
  gap: 11px;
  padding: 19px 18px 15px;
}
.heading-number {
  display: grid;
  flex: 0 0 27px;
  width: 27px;
  height: 27px;
  place-items: center;
  border-radius: 9px;
  background: #eaf1fa;
  color: #304f7e;
  font-size: 13px;
  font-weight: 800;
}
.heading-copy { min-width: 0; flex: 1; }
.heading-copy h2 { margin: 2px 0 5px; color: #213758; font-size: 14px; font-weight: 800; line-height: 1.35; }
.heading-copy p { margin: 0; color: #77869a; font-size: 11.5px; line-height: 1.45; }
.browser-tools { display: grid; gap: 11px; padding: 0 16px 14px; }
.browser-tools :deep(.v-field) { border-radius: 9px; }
.status-filter {
  display: flex;
  width: 100%;
  padding: 3px;
  border: 1px solid #e8edf3;
  border-radius: 9px;
  background: #f5f7fa;
  box-shadow: none;
}
.status-filter :deep(.v-btn) {
  flex: 1;
  min-width: 0;
  font-size: 11px;
  font-weight: 700;
  text-transform: none;
  letter-spacing: 0;
}
.result-row { display: flex; align-items: center; justify-content: space-between; min-height: 22px; gap: 8px; color: #7d8a9b; font-size: 11px; }
.browser-list {
  flex: 1 1 0;
  min-height: 220px;
  max-height: none;
  overflow-y: auto;
  overscroll-behavior: contain;
  border-top: 1px solid #edf0f5;
  padding: 8px;
  scrollbar-width: thin;
  scrollbar-color: #c5d0dc transparent;
}
.equipment-list { display: grid; gap: 5px; padding: 0; }
.equipment-option { min-width: 0; border: 1px solid transparent; transition: background 120ms ease, border-color 120ms ease; }
.equipment-option:hover:not(.v-list-item--disabled) { border-color: #e2eaf4; background: #f7fafe; }
.equipment-option--selected,
.equipment-option--selected:hover:not(.v-list-item--disabled) { border-color: #a8c0df; background: #edf4fc; box-shadow: inset 3px 0 #304f7e; }
.equipment-option :deep(.v-list-item__content) { min-width: 0; padding: 8px 0; }
.equipment-option :deep(.v-list-item-title) { display: block; min-width: 0; overflow: visible; white-space: normal; line-height: 1.4; }
.equipment-name { display: block; overflow-wrap: anywhere; color: #243750; font-size: 12px; font-weight: 750; }
.equipment-option__meta { display: flex; min-width: 0; align-items: center; gap: 7px; margin-top: 6px; color: #778699; font-size: 11px; }
.equipment-option__meta span:first-child { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.equipment-option__meta span:last-child { flex-shrink: 0; }
.meta-dot { color: #b7c3d0; }
.loading-list { display: grid; gap: 9px; padding: 5px 3px; }
.list-skeleton { height: 64px; border-radius: 9px; background: linear-gradient(90deg, #f1f4f8 20%, #e9eff6 48%, #f1f4f8 77%); background-size: 250% 100%; animation: shimmer 1.3s linear infinite; }
@keyframes shimmer { to { background-position-x: -250%; } }
.browser-empty { display: grid; justify-items: center; align-content: center; gap: 10px; min-height: 235px; padding: 24px 20px; text-align: center; }
.browser-empty strong { color: #31465f; font-size: 13px; }
.browser-empty p { max-width: 240px; margin: 0; color: #7b899b; font-size: 12px; line-height: 1.5; }
.empty-icon { display: grid; width: 48px; height: 48px; place-items: center; border-radius: 14px; background: #edf3fa; color: #5b7da5; }
.browser-footer { margin: 0; border-top: 1px solid #edf0f5; padding: 11px 16px; color: #8190a3; font-size: 10.5px; line-height: 1.45; }
@media (max-width: 1180px) {
  .master-browser { position: static; height: auto; }
  .browser-list { flex: 0 1 auto; max-height: 360px; }
}
@media (prefers-reduced-motion: reduce) { .list-skeleton { animation: none; } }
</style>
