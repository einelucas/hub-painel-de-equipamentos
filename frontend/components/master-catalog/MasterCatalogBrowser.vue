<script setup lang="ts">
import { computed } from "vue";
import { Layers, Search, X } from "lucide-vue-next";
import Badge from "~/components/ui/Badge.vue";
import Button from "~/components/ui/Button.vue";
import Input from "~/components/ui/Input.vue";
import LoadingSpinner from "~/components/ui/LoadingSpinner.vue";
import SearchableSelect from "~/components/ui/SearchableSelect.vue";
import type { MasterArea, MasterEquipment } from "~/types/masterCatalog";
import type { SearchableOption } from "~/types/ui";
import {
  activeRealAreas,
  areaSummary,
  buildAreaMap,
  componentCountLabel,
  filterEquipments,
  findUnassignedArea,
  fullAreaSummary,
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

const areaMap = computed(() => buildAreaMap(props.areas));
const realAreas = computed(() => activeRealAreas(props.areas));
const unassignedArea = computed(() => findUnassignedArea(props.areas));
const filterOptions = computed<SearchableOption[]>(() => [
  {
    id: "unassigned",
    label: unassignedArea.value?.name ?? "Sem área definida",
  },
  ...realAreas.value.map((area) => ({ id: area.id, label: area.name })),
]);
const visibleEquipments = computed(() =>
  filterEquipments(props.equipments, props.areas, props.search, props.filterArea),
);
const hasFilters = computed(() => Boolean(props.search.trim() || props.filterArea));
const resultsLabel = computed(() => {
  if (!props.equipments.length) return "Catálogo vazio";
  if (visibleEquipments.value.length === props.equipments.length) {
    return plural(props.equipments.length, "equipamento", "equipamentos");
  }
  return `${visibleEquipments.value.length} de ${plural(
    props.equipments.length,
    "equipamento",
    "equipamentos",
  )}`;
});

function updateSearch(value: string | number | undefined): void {
  emit("update:search", String(value ?? ""));
}

function clearSearch(): void {
  emit("update:search", "");
}

function clearFilters(): void {
  emit("clearFilters");
}
</script>

<template>
  <aside class="surface master-browser" aria-label="Equipamentos do catálogo">
    <header class="browser-head">
      <div>
        <h2>Equipamentos</h2>
        <p>{{ resultsLabel }}</p>
      </div>
      <LoadingSpinner v-if="props.loading" size="sm" />
    </header>

    <div class="browser-tools">
      <div class="search-box">
        <Search :size="15" aria-hidden="true" />
        <Input
          :model-value="props.search"
          type="search"
          placeholder="Buscar equipamento"
          aria-label="Buscar equipamento mestre"
          class="pl-9 pr-10"
          @update:model-value="updateSearch"
        />
        <Button
          v-if="props.search"
          variant="ghost"
          size="icon-sm"
          class="search-clear"
          aria-label="Limpar busca"
          @click="clearSearch"
        >
          <X aria-hidden="true" />
        </Button>
      </div>

      <SearchableSelect
        :model-value="props.filterArea"
        :options="filterOptions"
        label="Filtrar equipamentos por área"
        placeholder="Buscar área"
        empty-label="Todas as áreas"
        @update:model-value="emit('update:filterArea', $event)"
      />
    </div>

    <div class="browser-list" :aria-busy="props.loading">
      <div v-if="props.loading && !props.equipments.length" class="panel-state">
        <LoadingSpinner size="sm" label="Carregando catálogo..." />
      </div>
      <div v-else-if="!props.equipments.length" class="panel-empty">
        <span class="panel-empty__icon"><Layers :size="22" aria-hidden="true" /></span>
        <strong>Catálogo vazio</strong>
        <p>Use “Novo equipamento” ou importe um seed para começar.</p>
      </div>
      <div v-else-if="!visibleEquipments.length" class="panel-empty">
        <span class="panel-empty__icon"><Search :size="22" aria-hidden="true" /></span>
        <strong>Nenhum resultado</strong>
        <p>Ajuste a busca ou o filtro de área para encontrar o modelo.</p>
        <Button variant="outline" size="sm" @click="clearFilters">Limpar filtros</Button>
      </div>
      <ul v-else class="model-list">
        <li v-for="item in visibleEquipments" :key="item.id">
          <button
            type="button"
            class="model-item"
            :class="{ selected: item.id === props.selectedId }"
            :disabled="props.busy"
            :aria-pressed="item.id === props.selectedId"
            @click="emit('select', item)"
          >
            <span class="model-item__head">
              <span class="model-name" :title="item.name">{{ item.name }}</span>
              <Badge :variant="item.active ? 'success' : 'secondary'">
                {{ item.active ? "Ativo" : "Inativo" }}
              </Badge>
            </span>
            <span class="model-item__meta">
              <span class="model-area" :title="fullAreaSummary(item, areaMap)">
                <Layers :size="12" aria-hidden="true" /> {{ areaSummary(item, areaMap) }}
              </span>
              <span class="meta-dot" aria-hidden="true">·</span>
              <span>{{ componentCountLabel(item.components.length) }}</span>
            </span>
          </button>
        </li>
      </ul>
    </div>

    <footer v-if="props.equipments.length && visibleEquipments.length" class="browser-foot">
      <Button v-if="hasFilters" variant="ghost" size="sm" @click="clearFilters">
        Limpar filtros
      </Button>
      <span v-else>Clique em um equipamento para administrar</span>
    </footer>
  </aside>
</template>

<style scoped>
.master-browser {
  display: flex;
  min-width: 0;
  flex-direction: column;
  overflow: hidden;
}

.browser-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  padding: 17px 18px 12px;
}

.browser-head h2 {
  margin: 0;
  color: #213758;
  font-size: 17px;
  font-weight: 800;
}

.browser-head p {
  margin: 3px 0 0;
  color: #7b8798;
  font-size: 12px;
}

.browser-tools {
  display: grid;
  gap: 8px;
  padding: 0 18px 14px;
  border-bottom: 1px solid #edf1f5;
}

.search-box {
  position: relative;
  display: flex;
  align-items: center;
}

.search-box > svg {
  position: absolute;
  z-index: 1;
  top: 50%;
  left: 11px;
  color: #76869b;
  pointer-events: none;
  transform: translateY(-50%);
}

.search-clear {
  position: absolute;
  z-index: 1;
  top: 50%;
  right: 4px;
  transform: translateY(-50%);
}

.browser-list {
  min-height: 220px;
  max-height: min(62vh, 680px);
  overflow-y: auto;
  overscroll-behavior: contain;
  padding: 6px;
}

.panel-state,
.panel-empty {
  display: grid;
  place-items: center;
  gap: 8px;
  min-height: 200px;
  padding: 22px 18px;
  text-align: center;
}

.panel-empty__icon {
  display: grid;
  width: 48px;
  height: 48px;
  place-items: center;
  border-radius: 14px;
  background: #eef4fb;
  color: #557aa8;
}

.panel-empty strong {
  color: #2c405a;
  font-size: 14px;
}

.panel-empty p {
  max-width: 230px;
  margin: 0;
  color: #7d8a9c;
  font-size: 12px;
  line-height: 1.5;
}

.model-list {
  display: grid;
  gap: 3px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.model-item {
  display: grid;
  width: 100%;
  gap: 6px;
  border: 1px solid transparent;
  border-radius: 10px;
  padding: 10px 11px;
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
  transition:
    background 0.15s ease,
    border-color 0.15s ease;
}

.model-item:hover {
  background: #f7fafd;
}

.model-item:disabled {
  cursor: default;
  opacity: 0.7;
}

.model-item:disabled:hover {
  background: transparent;
}

.model-item.selected {
  border-color: #cfe0f4;
  background: #eef5fd;
}

.model-item.selected:disabled {
  background: #eef5fd;
}

.model-item__head,
.model-item__meta {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 8px;
}

.model-item__head {
  justify-content: space-between;
}

.model-name {
  min-width: 0;
  overflow: hidden;
  color: #243a57;
  font-size: 12.8px;
  font-weight: 750;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.model-item__meta {
  color: #77869a;
  font-size: 11px;
}

.model-area {
  display: inline-flex;
  min-width: 0;
  align-items: center;
  gap: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.model-area svg {
  flex: 0 0 auto;
  color: #6f8db3;
}

.meta-dot {
  color: #b1bcc9;
}

.browser-foot {
  display: flex;
  min-height: 35px;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  border-top: 1px solid #edf1f5;
  padding: 6px 12px 6px 18px;
  color: #8a96a7;
  font-size: 11px;
}

@media (max-width: 1180px) {
  .browser-list {
    max-height: 380px;
  }
}
</style>
