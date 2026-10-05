<script setup lang="ts">
import { computed } from "vue";
import { useImportState } from "~/composables/useImportState";

/** Passo 2: staging de cada arquivo (fase, contagens, problemas). Erro em qualquer arquivo impede avançar. */
const { batches, failures, totals, canProceed, busy, loadMappingOptions, reset } = useImportState();

const unknownFields = computed(() => [...new Set(batches.value.flatMap((batch) => batch.unknownFields))].sort());
const standby = computed(() =>
  batches.value.reduce((sum, batch) => sum + (batch.operationalStatuses.STANDBY ?? 0), 0),
);
</script>

<template>
  <div class="import-step" data-testid="import-step-analysis">
    <p v-if="batches.some((batch) => batch.alreadyStaged)" class="import-note" data-testid="import-already-staged">
      Arquivos já analisados nesta obra foram reaproveitados, sem duplicar dados.
    </p>

    <table class="files-table" data-testid="import-batch-table">
      <thead>
        <tr><th>Arquivo</th><th>Fase / grupo</th><th>Equip.</th><th>Comp.</th><th>Avisos</th><th>Erros</th></tr>
      </thead>
      <tbody>
        <tr v-for="batch in batches" :key="batch.batchId" :data-testid="`import-batch-${batch.batchId}`">
          <td class="file-name">{{ batch.fileName }}</td>
          <td>{{ batch.groups.join(", ") || "—" }}</td>
          <td>{{ batch.equipments }}</td>
          <td>{{ batch.components }}</td>
          <td>{{ batch.warnings }}</td>
          <td :class="{ 'has-errors': batch.errors > 0 }">{{ batch.errors }}</td>
        </tr>
        <tr v-for="failure in failures" :key="`f-${failure.fileName}`" class="failed" data-testid="import-file-failure">
          <td class="file-name">{{ failure.fileName }}</td>
          <td colspan="5">{{ failure.message }}</td>
        </tr>
      </tbody>
      <tfoot>
        <tr>
          <td colspan="2">Total ({{ batches.length }} arquivo{{ batches.length === 1 ? "" : "s" }})</td>
          <td data-testid="import-equipments">{{ totals.equipments }}</td>
          <td data-testid="import-components">{{ totals.components }}</td>
          <td colspan="2" />
        </tr>
      </tfoot>
    </table>

    <p v-if="standby" class="import-hint" data-testid="import-standby">
      {{ standby }} equipamento(s) em Standby na origem: serão importados com o estado operacional Standby.
    </p>

    <details v-for="batch in batches.filter((item) => item.issues.length)" :key="`i-${batch.batchId}`" class="import-details">
      <summary>Problemas em {{ batch.fileName }} ({{ batch.issues.length }})</summary>
      <ul>
        <li v-for="(issue, index) in batch.issues" :key="index" :class="{ error: issue.severity === 'error' }">
          <strong>{{ issue.message }}</strong>
          <span class="issue-meta">{{ issue.code }}<template v-if="issue.rowNumber"> · linha {{ issue.rowNumber }}</template><template v-if="issue.field"> · {{ issue.field }}</template></span>
        </li>
      </ul>
    </details>
    <details v-if="unknownFields.length" class="import-details" data-testid="import-unknown-fields">
      <summary>Colunas não reconhecidas pelo formato ({{ unknownFields.length }})</summary>
      <ul><li v-for="name in unknownFields" :key="name">{{ name }}</li></ul>
    </details>

    <p v-if="!canProceed" class="import-blocked" role="alert" data-testid="import-cannot-proceed">
      Há arquivo com erro. Corrija no Monday e envie o conjunto novamente; nada é importado parcialmente.
    </p>
    <div class="import-actions">
      <button type="button" class="btn" @click="reset">Enviar outros arquivos</button>
      <button
        type="button"
        class="btn primary"
        :disabled="!canProceed || busy"
        data-testid="import-to-mapping"
        @click="loadMappingOptions"
      >
        Continuar para o mapeamento
      </button>
    </div>
  </div>
</template>

<style scoped>
.import-step { display: grid; gap: 12px; }
.import-note { margin: 0; border-radius: 9px; background: #e8f1fc; padding: 8px 11px; color: #27456f; font-size: 12px; font-weight: 700; }
.import-hint { margin: 0; color: #65748a; font-size: 12px; }
.files-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.files-table th { color: #7a879a; font-size: 11px; font-weight: 750; text-align: left; }
.files-table th, .files-table td { border-bottom: 1px solid #f0f3f7; padding: 5px 6px; color: #2b3e58; }
.files-table tfoot td { font-weight: 800; }
.file-name { font-weight: 700; overflow-wrap: anywhere; }
.has-errors, .failed td { color: #a4453a; font-weight: 800; }
.import-details { color: #65748a; font-size: 12px; }
.import-details ul { display: grid; margin: 6px 0 0; padding: 0; gap: 5px; list-style: none; max-height: 160px; overflow-y: auto; }
.import-details li { display: grid; gap: 1px; color: #2b3e58; }
.import-details li.error strong { color: #a4453a; }
.issue-meta { color: #7a879a; font-size: 11px; }
.import-blocked { margin: 0; color: #a4453a; font-size: 12px; font-weight: 700; }
.import-actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 8px; }
</style>
