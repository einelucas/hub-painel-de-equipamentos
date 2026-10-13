<script setup lang="ts">
import { computed } from "vue";
import { ArrowRight } from "lucide-vue-next";
import SearchableSelect from "~/components/ui/SearchableSelect.vue";
import { MAPPING_SECTIONS } from "~/composables/useEquipmentImport";
import { useImportState } from "~/composables/useImportState";
import type { EapLocationStatus, ImportLocationValue, MappingSection } from "~/types/imports";

/**
 * Passo 3 (opcional): valor encontrado no Monday → cadastro existente no Hub.
 * Sem associação manual, o plano resolve sozinho: existente, novo (criado na
 * importação quando há dados comprovados no catálogo oficial/Monday/LGE) ou
 * pendente (não bloqueia; o vínculo fica vazio). Nada é inventado.
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
  RESOLVED: "Existente",
  CREATE: "Novo no Hub — será criado",
  CONFLICT: "Rótulo é o nome de outro código — bloqueia",
  UNRESOLVED: "Pendente",
  MULTIPLE: "Várias EAPs no valor — pendente",
  NONE: "Sem código EAP — pendente",
  NOT_FOUND: "EAP sem dados suficientes — pendente",
};

function automaticLabel(location: ImportLocationValue): string {
  if (location.status === "RESOLVED") return `Automático: ${location.eapCode} · ${location.eapName}`;
  if (location.status === "CREATE") return `Novo: ${location.plannedEapCode} · ${location.plannedEapName}`;
  return "Sem EAP (pendente)";
}

</script>

<template>
  <div class="import-step" data-testid="import-step-mapping">
    <p class="import-hint">
      Sem associação, o plano mostra cada item como existente, novo (criado na importação), conflito ou pendente —
      não é preciso cadastrar nada antes na administração.
    </p>
    <p v-if="catalogSections.length === 0 && locations.length === 0" class="empty" data-testid="import-mapping-empty">
      As planilhas não têm valores que dependam de cadastros do Hub.
    </p>

    <section
      v-for="section in catalogSections"
      :key="section.key"
      class="import-panel"
      :data-testid="`mapping-${section.key}`"
    >
      <div class="import-panel-head">
        <h4>{{ section.label }}</h4>
        <span class="import-count">{{ section.values.length }} valor{{ section.values.length === 1 ? "" : "es" }} na planilha</span>
      </div>
      <p v-if="section.options.length === 0" class="import-hint">
        Nenhum cadastro no Hub para esta seção ainda: o plano mostrará o que será criado ou ficará pendente.
      </p>
      <div class="mapping-rows">
        <div v-for="value in section.values" :key="value" class="mapping-row">
          <span class="mapping-source mono" :title="value">{{ value }}</span>
          <ArrowRight class="mapping-arrow" :size="15" aria-hidden="true" />
          <SearchableSelect
            :model-value="mapping[section.key][value] ?? ''"
            :options="section.options"
            :label="`${section.label}: ${value}`"
            placeholder="Digite para buscar"
            empty-label="Automático (existente, novo ou pendente)"
            :test-id="`mapping-select-${section.key}`"
            @update:model-value="setMapping(section.key, value, $event)"
          />
        </div>
      </div>
    </section>

    <section v-if="locations.length" class="import-panel" data-testid="mapping-eapNodes">
      <div class="import-panel-head">
        <h4>EAP (localização)</h4>
        <span class="import-count">{{ locations.length }} valor{{ locations.length === 1 ? "" : "es" }} na planilha</span>
      </div>
      <p class="import-hint">
        O código da EAP é lido do valor da planilha, sem o prefixo da obra ("2303 - …" → 03). EAP nova com nome
        comprovado é criada na importação; sem EAP única, o equipamento é importado sem EAP — nada é inventado.
        Escolha uma EAP só se tiver certeza.
      </p>
      <div class="mapping-rows">
        <div v-for="location in locations" :key="location.value" class="mapping-row" :data-testid="`eap-row-${location.status}`">
          <span class="mapping-source" :title="location.value">
            <span class="mono">{{ location.value }}</span>
            <small :class="['eap-status', `eap-status--${location.status.toLowerCase()}`]">
              {{ STATUS_LABELS[location.status] }}<template v-if="location.candidates.length > 1">: {{ location.candidates.join(", ") }}</template>
              · {{ location.equipments }} equip.
              <template v-if="location.status !== 'RESOLVED' && location.issueMessage"> · {{ location.issueMessage }}</template>
            </small>
          </span>
          <ArrowRight class="mapping-arrow" :size="15" aria-hidden="true" />
          <SearchableSelect
            :model-value="mapping.eapNodes[location.value] ?? ''"
            :options="options.eapNodes"
            :label="`EAP: ${location.value}`"
            placeholder="Buscar por código ou nome"
            :empty-label="automaticLabel(location)"
            test-id="mapping-select-eapNodes"
            @update:model-value="setMapping('eapNodes', location.value, $event)"
          />
        </div>
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
.empty { margin: 0; border: 1px dashed var(--rule); border-radius: 12px; padding: 18px; color: var(--muted); font-size: 12.5px; text-align: center; }
.mapping-rows { display: grid; }
.mapping-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1.15fr);
  align-items: center;
  gap: 12px;
  padding: 8px 0;
  border-top: 1px solid #edf1f6;
}
.mapping-row:first-child { border-top: 0; padding-top: 2px; }
.mapping-source { display: grid; gap: 2px; min-width: 0; overflow: hidden; color: var(--ink); font-size: 12.5px; font-weight: 600; text-overflow: ellipsis; white-space: nowrap; }
.mapping-source > .mono { overflow: hidden; text-overflow: ellipsis; }
.mapping-arrow { color: #a3b1c4; }
.mapping-row > :last-child { min-width: 0; }
.eap-status { overflow: hidden; font-size: 10.5px; font-weight: 700; text-overflow: ellipsis; white-space: normal; }
.eap-status--resolved { color: var(--go); }
.eap-status--create { color: #2d5c9a; }
.eap-status--conflict { color: var(--stop); }
.eap-status--multiple, .eap-status--not_found, .eap-status--unresolved { color: var(--caution); }
.eap-status--none { color: var(--muted); }
@media (max-width: 760px) {
  .mapping-row { grid-template-columns: 1fr; gap: 6px; }
  .mapping-arrow { display: none; }
}
</style>
