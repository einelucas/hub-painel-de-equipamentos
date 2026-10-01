<script setup lang="ts">
import { computed } from "vue";
import { X } from "lucide-vue-next";
import type { CatalogItem } from "~/types/equipment";
import { EQUIPMENT_STAGES } from "~/utils/stages";

defineProps<{
  areas: CatalogItem[];
  disciplines: CatalogItem[];
  /** Área pertence à Unidade: sem unidade selecionada não há catálogo de áreas. */
  areaDisabled: boolean;
}>();
const emit = defineEmits<{ change: []; clear: [] }>();

const areaId = defineModel<string | null>("areaId", { required: true });
const disciplineId = defineModel<string | null>("disciplineId", { required: true });
const stage = defineModel<number | null>("stage", { required: true });

const hasActive = computed(() => areaId.value !== null || disciplineId.value !== null || stage.value !== null);

function selected(event: Event): string {
  return (event.target as HTMLSelectElement).value;
}

function onArea(event: Event): void {
  areaId.value = selected(event) || null;
  emit("change");
}

function onStage(event: Event): void {
  const value = selected(event);
  stage.value = value === "" ? null : Number(value);
  emit("change");
}

function onDiscipline(event: Event): void {
  disciplineId.value = selected(event) || null;
  emit("change");
}
</script>

<template>
  <div class="dashboard-filters" data-testid="dashboard-filters">
    <label class="field">
      <span>Área</span>
      <select
        :value="areaId ?? ''"
        :disabled="areaDisabled"
        :title="areaDisabled ? 'Selecione uma unidade para filtrar por área' : undefined"
        data-testid="dashboard-filter-area"
        @change="onArea"
      >
        <option value="">Todas as áreas</option>
        <option v-for="item in areas" :key="item.id" :value="item.id">{{ item.name }}</option>
      </select>
    </label>
    <label class="field">
      <span>Fase</span>
      <select :value="stage === null ? '' : String(stage)" data-testid="dashboard-filter-stage" @change="onStage">
        <option value="">Todas as fases</option>
        <option v-for="(name, index) in EQUIPMENT_STAGES" :key="name" :value="String(index)">
          {{ index }} · {{ name }}
        </option>
      </select>
    </label>
    <label class="field">
      <span>Disciplina</span>
      <select :value="disciplineId ?? ''" data-testid="dashboard-filter-discipline" @change="onDiscipline">
        <option value="">Todas as disciplinas</option>
        <option v-for="item in disciplines" :key="item.id" :value="item.id">{{ item.name }}</option>
      </select>
    </label>
    <button
      v-if="hasActive"
      type="button"
      class="clear-filters"
      data-testid="dashboard-filters-clear"
      @click="emit('clear')"
    >
      <X :size="13" /> Limpar filtros
    </button>
  </div>
</template>

<style scoped>
/* display: contents deixa cada campo ser um item próprio da barra de filtros (quebra de linha responsiva). */
.dashboard-filters { display: contents; }
.field { flex: 1 1 170px; }
.clear-filters {
  display: inline-flex;
  flex: 0 0 auto;
  align-self: flex-end;
  align-items: center;
  gap: 5px;
  min-height: 39px;
  border: 0;
  padding: 0 4px;
  background: transparent;
  color: #304f7e;
  font-size: 12px;
  font-weight: 750;
  cursor: pointer;
}
.clear-filters:hover { text-decoration: underline; }
@media (max-width: 640px) { .field { flex-basis: 100%; } }
</style>
