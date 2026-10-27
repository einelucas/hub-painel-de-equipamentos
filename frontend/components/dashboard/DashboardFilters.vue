<script setup lang="ts">
import Button from "~/components/ui/Button.vue";
import { computed } from "vue";
import { X } from "lucide-vue-next";
import SearchableSelect from "~/components/ui/SearchableSelect.vue";
import type { CatalogItem } from "~/types/equipment";
import { STAGE_OPTIONS, toOptions } from "~/utils/selectOptions";

const props = defineProps<{
  areas: CatalogItem[];
  disciplines: CatalogItem[];
}>();
const emit = defineEmits<{ change: []; clear: [] }>();

const areaId = defineModel<string | null>("areaId", { required: true });
const disciplineId = defineModel<string | null>("disciplineId", { required: true });
const stage = defineModel<number | null>("stage", { required: true });

const hasActive = computed(() => areaId.value !== null || disciplineId.value !== null || stage.value !== null);

const areaOptions = computed(() => toOptions(props.areas));
const disciplineOptions = computed(() => toOptions(props.disciplines));

function onArea(value: string): void {
  areaId.value = value || null;
  emit("change");
}

function onStage(value: string): void {
  stage.value = value === "" ? null : Number(value);
  emit("change");
}

function onDiscipline(value: string): void {
  disciplineId.value = value || null;
  emit("change");
}
</script>

<template>
  <div class="dashboard-filters" data-testid="dashboard-filters">
    <div class="field">
      <span>Área</span>
      <SearchableSelect
        :model-value="areaId ?? ''"
        :options="areaOptions"
        label="Área"
        placeholder="Buscar por código ou nome"
        empty-label="Todas as áreas"
        test-id="dashboard-filter-area"
        @change="onArea"
      />
    </div>
    <div class="field">
      <span>Fase</span>
      <SearchableSelect
        :model-value="stage === null ? '' : String(stage)"
        :options="STAGE_OPTIONS"
        :sorted="false"
        label="Fase"
        placeholder="Buscar fase"
        empty-label="Todas as fases"
        test-id="dashboard-filter-stage"
        @change="onStage"
      />
    </div>
    <div class="field">
      <span>Disciplina</span>
      <SearchableSelect
        :model-value="disciplineId ?? ''"
        :options="disciplineOptions"
        label="Disciplina"
        placeholder="Buscar disciplina"
        empty-label="Todas as disciplinas"
        test-id="dashboard-filter-discipline"
        @change="onDiscipline"
      />
    </div>
    <Button
      v-if="hasActive"
      type="button"
      class="clear-filters"
      data-testid="dashboard-filters-clear"
      variant="ghost"
      @click="emit('clear')"
    >
      <X :size="13" /> Limpar filtros
    </Button>
  </div>
</template>

<style scoped>
/* display: contents deixa cada campo ser um item próprio da barra de filtros (quebra de linha responsiva). */
.dashboard-filters { display: contents; }
.field { flex: 1 1 170px; }
@media (max-width: 640px) { .field { flex-basis: 100%; } }
</style>
