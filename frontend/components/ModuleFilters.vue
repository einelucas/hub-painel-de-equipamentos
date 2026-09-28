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
.filter-grid { display: flex; flex-wrap: wrap; align-items: flex-end; gap: 14px 12px; }
.filter-grid > .field { flex: 1 1 240px; }
/* display: contents deixa cada campo do slot participar da quebra de linha como item próprio */
.filter-extra { display: contents; }
.filter-extra > :slotted(.field) { flex: 1 1 170px; }
.filter-extra > :slotted(.field-wide) { flex: 2 1 300px; }
.filter-extra > :slotted(.field-inline) { flex: 0 0 auto; }
.filter-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-left: auto; }
.filter-hint { margin: 10px 0 0; color: #8b96a5; font-size: 11.5px; }
@media (max-width: 640px) { .filter-grid > .field, .filter-extra > :slotted(.field) { flex-basis: 100%; } .filter-actions { width: 100%; } .filter-actions .btn { flex: 1; } }
</style>
