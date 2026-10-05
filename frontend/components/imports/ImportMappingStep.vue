<script setup lang="ts">
import { computed } from "vue";
import { MAPPING_SECTIONS } from "~/composables/useEquipmentImport";
import { useImportState } from "~/composables/useImportState";

/**
 * Passo 3: valor encontrado no Monday → cadastro existente no Hub.
 * Nada é criado automaticamente; sem correspondente, o plano fica bloqueado.
 */
const { batch, mapping, options, busy, setMapping, buildPlan } = useImportState();

const sections = computed(() =>
  MAPPING_SECTIONS.map((section) => ({
    ...section,
    values: batch.value?.sourceValues[section.key] ?? [],
    options: options.value[section.key],
  })).filter((section) => section.values.length > 0),
);

function onSelect(section: (typeof MAPPING_SECTIONS)[number]["key"], source: string, event: Event): void {
  setMapping(section, source, (event.target as HTMLSelectElement).value);
}
</script>

<template>
  <div class="import-step" data-testid="import-step-mapping">
    <p class="import-hint">
      Associe cada valor encontrado na planilha a um cadastro existente no Hub. Se não houver correspondente,
      corrija o cadastro na administração; o plano mostrará o item como bloqueado.
    </p>
    <p v-if="sections.length === 0" class="import-hint" data-testid="import-mapping-empty">
      A planilha não tem valores que dependam de cadastros do Hub.
    </p>

    <section v-for="section in sections" :key="section.key" class="mapping-section" :data-testid="`mapping-${section.key}`">
      <h4>{{ section.label }}</h4>
      <p v-if="section.options.length === 0" class="import-hint">Nenhum cadastro disponível no Hub para esta seção.</p>
      <div v-for="value in section.values" :key="value" class="mapping-row">
        <span class="mapping-source" :title="value">{{ value }}</span>
        <span aria-hidden="true">→</span>
        <select
          :value="mapping[section.key][value] ?? ''"
          :aria-label="`${section.label}: ${value}`"
          :data-testid="`mapping-select-${section.key}`"
          @change="onSelect(section.key, value, $event)"
        >
          <option value="">Sem correspondente</option>
          <option v-for="option in section.options" :key="option.id" :value="option.id">{{ option.label }}</option>
        </select>
      </div>
    </section>

    <div class="import-actions">
      <button type="button" class="btn primary" :disabled="busy" data-testid="import-build-plan" @click="buildPlan">
        {{ busy ? "Gerando plano..." : "Gerar plano" }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.import-step { display: grid; gap: 12px; }
.import-hint { margin: 0; color: #8b96a5; font-size: 11.5px; }
.mapping-section { display: grid; gap: 6px; border: 1px solid #e4e9f0; border-radius: 10px; padding: 10px 12px; }
.mapping-section h4 { margin: 0; color: #2b3e58; font-size: 12px; font-weight: 800; }
.mapping-row { display: grid; grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr); align-items: center; gap: 8px; color: #65748a; font-size: 12px; }
.mapping-source { overflow: hidden; color: #2b3e58; font-weight: 700; text-overflow: ellipsis; white-space: nowrap; }
.mapping-row select { min-width: 0; }
.import-actions { display: flex; justify-content: flex-end; }
@media (max-width: 620px) { .mapping-row { grid-template-columns: 1fr; } .mapping-row > span[aria-hidden] { display: none; } }
</style>
