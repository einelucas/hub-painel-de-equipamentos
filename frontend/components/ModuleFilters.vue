<script setup lang="ts">
import Button from "~/components/ui/Button.vue";
import { computed } from "vue";
import { Boxes, Building2, MapPin, RefreshCw } from "lucide-vue-next";
import FloatingFilterSelect from "~/components/ui/FloatingFilterSelect.vue";
import { toOptions } from "~/utils/selectOptions";

const props = withDefaults(defineProps<{
  refreshing?: boolean;
  showRefresh?: boolean;
  showProjectContext?: boolean;
}>(), {
  refreshing: false,
  showRefresh: true,
  showProjectContext: false,
});
const emit = defineEmits<{ change: [] }>();
const context = useModuleContextStore();

const unitOptions = computed(() => toOptions(context.units));
const projectContextOptions = computed(() => toOptions(context.projectContexts));
const equipmentOptions = computed(() => toOptions(context.equipmentOptions));

async function onUnit(value: string): Promise<void> {
  await context.setUnit(value);
  emit("change");
}

async function onProjectContext(value: string): Promise<void> {
  await context.setProjectContext(value);
  emit("change");
}

function onEquipment(value: string): void {
  context.setEquipment(value);
  emit("change");
}
</script>

<template>
  <section class="surface filter-surface" aria-label="Filtros globais do módulo" :aria-busy="context.loading || context.optionsLoading">
    <div class="filter-grid">
      <div class="field">
        <!-- Com uma única unidade disponível não há a opção "todas". -->
        <FloatingFilterSelect
          :model-value="context.selectedUnit"
          :options="unitOptions"
          :disabled="context.loading"
          :clearable="context.units.length !== 1"
          :icon="Building2"
          label="Unidade"
          placeholder="Buscar unidade"
          empty-label="Todas as unidades"
          test-id="filter-unit"
          @change="onUnit"
        />
      </div>
      <div v-if="props.showProjectContext" class="field">
        <FloatingFilterSelect
          :model-value="context.selectedProjectContext"
          :options="projectContextOptions"
          :disabled="!context.selectedUnit || context.loading || context.optionsLoading"
          :icon="MapPin"
          label="Obra"
          placeholder="Buscar obra"
          empty-label="Todas as obras"
          test-id="filter-project-context"
          @change="onProjectContext"
        />
      </div>
      <div class="field">
        <FloatingFilterSelect
          :model-value="context.selectedEquipment"
          :options="equipmentOptions"
          :disabled="!context.selectedUnit || context.loading || context.optionsLoading"
          :icon="Boxes"
          label="Equipamento"
          placeholder="Buscar equipamento"
          empty-label="Todos os equipamentos"
          test-id="filter-equipment"
          @change="onEquipment"
        />
      </div>
      <div class="filter-extra"><slot /></div>
      <div v-if="props.showRefresh" class="filter-actions">
        <Button :disabled="props.refreshing" :loading="props.refreshing" variant="outline" @click="emit('change')">
          <RefreshCw v-if="!(props.refreshing)" :size="15" /> {{ props.refreshing ? "Atualizando..." : "Atualizar" }}
        </Button>
        <slot name="actions" />
      </div>
    </div>
    <p v-if="context.loading || context.optionsLoading" class="filter-hint filter-loading" role="status">
      <span class="spinner-small" aria-hidden="true" /> Carregando opções de filtro...
    </p>
    <p v-else-if="!context.selectedUnit" class="filter-hint">
      Sem unidade selecionada os números consolidam todas as unidades disponíveis para você.
    </p>
  </section>
</template>

<style scoped>
.filter-surface { padding: 16px 18px; }
.filter-grid { display: flex; flex-wrap: wrap; align-items: flex-end; gap: 14px 12px; }
.filter-grid > .field { flex: 1 1 240px; min-width: 0; }
/* display: contents deixa cada campo do slot participar da quebra de linha como item próprio */
.filter-extra { display: contents; }
.filter-extra > :slotted(.field) { flex: 1 1 170px; min-width: 0; }
.filter-extra > :slotted(.field-wide) { flex: 2 1 300px; }
.filter-extra > :slotted(.field-inline) { flex: 0 0 auto; }
.filter-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-left: auto; }
.filter-loading { display: flex; align-items: center; gap: 7px; }
.filter-hint { margin: 10px 0 0; color: #8b96a5; font-size: 11.5px; }
@media (max-width: 640px) { .filter-grid > .field, .filter-extra > :slotted(.field) { flex-basis: 100%; } .filter-actions { width: 100%; } .filter-actions .el-button { flex: 1; } }
</style>
