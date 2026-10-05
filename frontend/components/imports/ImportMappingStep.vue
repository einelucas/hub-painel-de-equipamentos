<script setup lang="ts">
import { computed } from "vue";
import { MAPPING_SECTIONS } from "~/composables/useEquipmentImport";
import { useImportState } from "~/composables/useImportState";
import type { EapLocationStatus, MappingSection } from "~/types/imports";

/**
 * Passo 3: valor encontrado no Monday → cadastro existente no Hub.
 * Nada é criado automaticamente. Localização → EAP: códigos únicos e válidos
 * já resolvem sozinhos; o resto fica pendente até uma escolha explícita.
 */
const { sourceValues, mapping, options, busy, setMapping, buildPlan } = useImportState();

const catalogSections = computed(() =>
  MAPPING_SECTIONS.filter((section) => section.key !== "eapNodes")
    .map((section) => ({
      ...section,
      values: sourceValues.value[section.key as Exclude<MappingSection, "eapNodes">],
      options: options.value[section.key],
    }))
    .filter((section) => section.values.length > 0),
);
const locations = computed(() => sourceValues.value.locations);

const STATUS_LABELS: Record<EapLocationStatus, string> = {
  RESOLVED: "EAP identificada",
  MULTIPLE: "Várias EAPs no valor",
  NONE: "Sem código EAP",
  NOT_FOUND: "EAP fora do catálogo",
};

function onSelect(section: MappingSection, source: string, event: Event): void {
  setMapping(section, source, (event.target as HTMLSelectElement).value);
}
</script>

<template>
  <div class="import-step" data-testid="import-step-mapping">
    <p class="import-hint">
      Associe cada valor encontrado nas planilhas a um cadastro existente no Hub. Se não houver correspondente,
      corrija o cadastro na administração; o plano mostrará o item como bloqueado.
    </p>
    <p v-if="catalogSections.length === 0 && locations.length === 0" class="import-hint" data-testid="import-mapping-empty">
      As planilhas não têm valores que dependam de cadastros do Hub.
    </p>

    <section
      v-for="section in catalogSections"
      :key="section.key"
      class="mapping-section"
      :data-testid="`mapping-${section.key}`"
    >
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

    <section v-if="locations.length" class="mapping-section" data-testid="mapping-eapNodes">
      <h4>EAP (localização)</h4>
      <p class="import-hint">
        O código da EAP é lido do valor da planilha, sem o prefixo da obra ("2303 - …" → 03). Sem EAP única e
        cadastrada, o equipamento é importado sem EAP — nada é inventado. Escolha uma EAP só se tiver certeza.
      </p>
      <div v-for="location in locations" :key="location.value" class="mapping-row" :data-testid="`eap-row-${location.status}`">
        <span class="mapping-source" :title="location.value">
          {{ location.value }}
          <small :class="['eap-status', `eap-status--${location.status.toLowerCase()}`]">
            {{ STATUS_LABELS[location.status] }}<template v-if="location.candidates.length > 1">: {{ location.candidates.join(", ") }}</template>
            · {{ location.equipments }} equip.
          </small>
        </span>
        <span aria-hidden="true">→</span>
        <select
          :value="mapping.eapNodes[location.value] ?? ''"
          :aria-label="`EAP: ${location.value}`"
          data-testid="mapping-select-eapNodes"
          @change="onSelect('eapNodes', location.value, $event)"
        >
          <option value="">
            {{ location.status === "RESOLVED" ? `Automático: ${location.eapCode} · ${location.eapName}` : "Sem EAP (pendente)" }}
          </option>
          <option v-for="option in options.eapNodes" :key="option.id" :value="option.id">{{ option.label }}</option>
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
.mapping-section { display: grid; gap: 6px; border: 1px solid #e4e9f0; border-radius: 10px; padding: 10px 12px; max-height: 320px; overflow-y: auto; }
.mapping-section h4 { margin: 0; color: #2b3e58; font-size: 12px; font-weight: 800; }
.mapping-row { display: grid; grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr); align-items: center; gap: 8px; color: #65748a; font-size: 12px; }
.mapping-source { display: grid; overflow: hidden; color: #2b3e58; font-weight: 700; text-overflow: ellipsis; }
.mapping-row select { min-width: 0; }
.eap-status { font-size: 10.5px; font-weight: 700; }
.eap-status--resolved { color: #477a32; }
.eap-status--multiple, .eap-status--not_found { color: #8a5a12; }
.eap-status--none { color: #7a879a; }
.import-actions { display: flex; justify-content: flex-end; }
@media (max-width: 620px) { .mapping-row { grid-template-columns: 1fr; } .mapping-row > span[aria-hidden] { display: none; } }
</style>
