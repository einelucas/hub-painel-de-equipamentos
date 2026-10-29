<script setup lang="ts">
import { computed } from "vue";
import { VBtn } from "vuetify/components";
import { useImportState } from "~/composables/useImportState";

/** Passo 2: staging de cada arquivo (fase, contagens, problemas). Erro em qualquer arquivo impede avançar. */
const { batches, failures, totals, canProceed, busy, loadMappingOptions, reset } = useImportState();

const unknownFields = computed(() => [...new Set(batches.value.flatMap((batch) => batch.unknownFields))].sort());
const warnings = computed(() => batches.value.reduce((sum, batch) => sum + batch.warnings, 0));
const errors = computed(() => batches.value.reduce((sum, batch) => sum + batch.errors, 0) + failures.value.length);
const standby = computed(() =>
  batches.value.reduce((sum, batch) => sum + (batch.operationalStatuses.STANDBY ?? 0), 0),
);
</script>

<template>
  <div class="import-step" data-testid="import-step-analysis">
    <p v-if="batches.some((batch) => batch.alreadyStaged)" class="note" data-testid="import-already-staged">
      Arquivos já analisados nesta obra foram reaproveitados, sem duplicar dados.
    </p>

    <dl class="import-ledger" aria-label="Totais lidos">
      <div><dt>Arquivos</dt><dd>{{ batches.length + failures.length }}</dd></div>
      <div><dt>Equipamentos</dt><dd>{{ totals.equipments }}</dd></div>
      <div><dt>Componentes</dt><dd>{{ totals.components }}</dd></div>
      <div :class="{ 'is-caution': warnings > 0 }"><dt>Avisos</dt><dd>{{ warnings }}</dd></div>
      <div :class="errors > 0 ? 'is-stop' : 'is-go'"><dt>Erros</dt><dd>{{ errors }}</dd></div>
    </dl>

    <table class="import-table" data-testid="import-batch-table">
      <thead>
        <tr><th>Arquivo</th><th>Fase / grupo</th><th class="num">Equip.</th><th class="num">Comp.</th><th class="num">Avisos</th><th class="num">Erros</th></tr>
      </thead>
      <tbody>
        <tr v-for="batch in batches" :key="batch.batchId" :data-testid="`import-batch-${batch.batchId}`">
          <td class="file-name mono">{{ batch.fileName }}</td>
          <td>{{ batch.groups.join(", ") || "—" }}</td>
          <td class="num">{{ batch.equipments }}</td>
          <td class="num">{{ batch.components }}</td>
          <td class="num">{{ batch.warnings }}</td>
          <td class="num" :class="{ 'has-errors': batch.errors > 0 }">{{ batch.errors }}</td>
        </tr>
        <tr v-for="failure in failures" :key="`f-${failure.fileName}`" class="failed" data-testid="import-file-failure">
          <td class="file-name mono">{{ failure.fileName }}</td>
          <td colspan="5">{{ failure.message }}</td>
        </tr>
      </tbody>
      <tfoot>
        <tr>
          <td colspan="2">Total ({{ batches.length }} arquivo{{ batches.length === 1 ? "" : "s" }})</td>
          <td class="num" data-testid="import-equipments">{{ totals.equipments }}</td>
          <td class="num" data-testid="import-components">{{ totals.components }}</td>
          <td colspan="2" />
        </tr>
      </tfoot>
    </table>

    <p v-if="standby" class="import-hint" data-testid="import-standby">
      {{ standby }} equipamento(s) em Standby na origem: serão importados com o estado operacional Standby.
    </p>

    <details v-for="batch in batches.filter((item) => item.issues.length)" :key="`i-${batch.batchId}`" class="import-details">
      <summary>Problemas em <span class="mono">{{ batch.fileName }}</span> <span class="import-count">({{ batch.issues.length }})</span></summary>
      <ul>
        <li v-for="(issue, index) in batch.issues" :key="index" :class="{ error: issue.severity === 'error' }">
          <strong>{{ issue.message }}</strong>
          <span class="issue-meta mono">{{ issue.code }}<template v-if="issue.rowNumber"> · linha {{ issue.rowNumber }}</template><template v-if="issue.field"> · {{ issue.field }}</template></span>
        </li>
      </ul>
    </details>
    <details v-if="unknownFields.length" class="import-details" data-testid="import-unknown-fields">
      <summary>Colunas não reconhecidas pelo formato <span class="import-count">({{ unknownFields.length }})</span></summary>
      <ul><li v-for="name in unknownFields" :key="name" class="mono">{{ name }}</li></ul>
    </details>

    <p v-if="!canProceed" class="blocked" role="alert" data-testid="import-cannot-proceed">
      Há arquivo com erro. Corrija no Monday e envie o conjunto novamente; nada é importado parcialmente.
    </p>
    <div class="import-actions">
      <VBtn variant="outlined" @click="reset">Enviar outros arquivos</VBtn>
      <VBtn
        variant="tonal"
        :disabled="!canProceed"
        :loading="busy"
        data-testid="import-to-mapping"
        @click="loadMappingOptions"
      >
        {{ busy ? "Carregando cadastros..." : "Continuar para o mapeamento" }}
      </VBtn>
    </div>
  </div>
</template>

<style scoped>
.note { margin: 0; border-left: 3px solid var(--steel); border-radius: 8px; background: #e8f1fc; padding: 9px 12px; color: #27456f; font-size: 12px; font-weight: 700; }
.file-name { font-weight: 600; overflow-wrap: anywhere; }
.has-errors, .failed td { color: var(--stop); font-weight: 800; }
.import-details { border: 1px solid var(--rule); border-radius: 12px; padding: 10px 14px; color: var(--muted); font-size: 12px; }
.import-details summary { color: var(--ink); font-weight: 700; cursor: pointer; }
.import-details ul { display: grid; margin: 10px 0 0; padding: 0; gap: 7px; list-style: none; max-height: 220px; overflow-y: auto; }
.import-details li { display: grid; gap: 1px; color: var(--ink); }
.import-details li.error strong { color: var(--stop); }
.issue-meta { color: var(--muted); font-size: 11px; }
.blocked { margin: 0; border-left: 3px solid var(--stop); border-radius: 8px; background: var(--stop-wash); padding: 9px 12px; color: var(--stop); font-size: 12px; font-weight: 700; }
</style>
