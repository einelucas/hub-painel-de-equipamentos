<script setup lang="ts">
import { RefreshCw } from "lucide-vue-next";

const props = withDefaults(defineProps<{ refreshing?: boolean; showRefresh?: boolean }>(), {
  refreshing: false,
  showRefresh: true,
});
const emit = defineEmits<{ change: [] }>();
const context = useModuleContextStore();

async function onUnit(event: Event): Promise<void> {
  await context.setUnit((event.target as HTMLSelectElement).value);
  emit("change");
}

function onEquipment(event: Event): void {
  context.setEquipment((event.target as HTMLSelectElement).value);
  emit("change");
}
</script>

<template>
  <section class="surface filter-surface" aria-label="Filtros globais do módulo">
    <div class="filter-grid">
      <label class="field">
        <span>Unidade</span>
        <select
          :value="context.selectedUnit"
          :disabled="context.loading"
          data-testid="filter-unit"
          @change="onUnit"
        >
          <option v-if="context.units.length !== 1" value="">Todas as unidades</option>
          <option v-for="unit in context.units" :key="unit.id" :value="unit.id">
            {{ unit.code }} · {{ unit.name }}
          </option>
        </select>
      </label>
      <label class="field">
        <span>Equipamento</span>
        <select
          :value="context.selectedEquipment"
          :disabled="!context.selectedUnit || context.loading"
          data-testid="filter-equipment"
          @change="onEquipment"
        >
          <option value="">Todos os equipamentos</option>
          <option v-for="equipment in context.equipmentOptions" :key="equipment.id" :value="equipment.id">
            {{ equipment.name }}
          </option>
        </select>
      </label>
      <div class="filter-extra"><slot /></div>
      <div v-if="props.showRefresh" class="filter-actions">
        <button class="btn" :disabled="props.refreshing" @click="emit('change')">
          <RefreshCw :size="15" /> Atualizar
        </button>
        <slot name="actions" />
      </div>
    </div>
    <p v-if="!context.selectedUnit" class="filter-hint">
      Sem unidade selecionada os números consolidam todas as unidades disponíveis para você.
    </p>
  </section>
</template>

<style scoped>
.filter-surface { padding: 16px 18px; }
.filter-grid { display: grid; grid-template-columns: minmax(190px, .8fr) minmax(220px, 1fr) minmax(0, 1.3fr) auto; align-items: end; gap: 12px; }
.filter-extra { display: flex; align-items: end; gap: 10px; }
.filter-actions { display: flex; flex-wrap: wrap; gap: 8px; }
.filter-hint { margin: 10px 0 0; color: #8b96a5; font-size: 11.5px; }
@media (max-width: 1050px) { .filter-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 640px) { .filter-grid { grid-template-columns: 1fr; } .filter-actions { justify-content: stretch; } .filter-actions .btn { flex: 1; } }
</style>
