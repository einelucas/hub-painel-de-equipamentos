<script setup lang="ts">
import { computed } from "vue";
import { useImportState } from "~/composables/useImportState";

/** Passo 2: resumo do staging e problemas por severidade. Erros impedem avançar. */
const { batch, busy, loadMappingOptions, reset } = useImportState();

const errors = computed(() => batch.value?.issues.filter((issue) => issue.severity === "error") ?? []);
const warnings = computed(() => batch.value?.issues.filter((issue) => issue.severity !== "error") ?? []);
</script>

<template>
  <div v-if="batch" class="import-step" data-testid="import-step-analysis">
    <p v-if="batch.alreadyStaged" class="import-note" data-testid="import-already-staged">
      Este arquivo já tinha sido analisado nesta obra. A análise existente foi reaproveitada, sem duplicar dados.
    </p>

    <dl class="import-summary">
      <div><dt>Arquivo</dt><dd>{{ batch.fileName }}</dd></div>
      <div><dt>Board</dt><dd>{{ batch.boardTitle ?? "Não identificado" }}</dd></div>
      <div><dt>Formato</dt><dd>{{ batch.profile ? `${batch.profile.profileId} v${batch.profile.version}` : "—" }}</dd></div>
      <div><dt>Equipamentos</dt><dd data-testid="import-equipments">{{ batch.equipments }}</dd></div>
      <div><dt>Componentes</dt><dd data-testid="import-components">{{ batch.components }}</dd></div>
      <div><dt>Erros</dt><dd data-testid="import-errors">{{ batch.errors }}</dd></div>
      <div><dt>Avisos</dt><dd data-testid="import-warnings">{{ batch.warnings }}</dd></div>
      <div><dt>Identidade frágil</dt><dd>{{ batch.fragileIdentities }}</dd></div>
      <div><dt>Status desconhecidos</dt><dd>{{ batch.unknownStatuses }}</dd></div>
    </dl>

    <section v-if="errors.length" class="issues issues--error" data-testid="import-error-list">
      <h4>Erros ({{ errors.length }})</h4>
      <ul>
        <li v-for="(issue, index) in errors" :key="`e${index}`">
          <strong>{{ issue.message }}</strong>
          <span class="issue-meta">{{ issue.code }}<template v-if="issue.rowNumber"> · linha {{ issue.rowNumber }}</template><template v-if="issue.field"> · {{ issue.field }}</template></span>
        </li>
      </ul>
    </section>
    <section v-if="warnings.length" class="issues issues--warning" data-testid="import-warning-list">
      <h4>Avisos ({{ warnings.length }})</h4>
      <ul>
        <li v-for="(issue, index) in warnings" :key="`w${index}`">
          <strong>{{ issue.message }}</strong>
          <span class="issue-meta">{{ issue.code }}<template v-if="issue.rowNumber"> · linha {{ issue.rowNumber }}</template><template v-if="issue.field"> · {{ issue.field }}</template></span>
        </li>
      </ul>
    </section>
    <details v-if="batch.unknownFields.length" class="import-details">
      <summary>Colunas não reconhecidas pelo formato ({{ batch.unknownFields.length }})</summary>
      <ul><li v-for="name in batch.unknownFields" :key="name">{{ name }}</li></ul>
    </details>

    <p v-if="!batch.canProceed" class="import-blocked" role="alert" data-testid="import-cannot-proceed">
      A planilha tem erros. Corrija o arquivo no Monday e envie novamente.
    </p>
    <div class="import-actions">
      <button type="button" class="btn" @click="reset">Enviar outro arquivo</button>
      <button
        type="button"
        class="btn primary"
        :disabled="!batch.canProceed || busy"
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
.import-summary { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); margin: 0; gap: 8px 14px; }
.import-summary div { display: grid; gap: 2px; }
.import-summary dt { color: #7a879a; font-size: 11px; }
.import-summary dd { margin: 0; color: #2b3e58; font-size: 12.5px; font-weight: 750; overflow-wrap: anywhere; }
.issues { border-radius: 10px; padding: 9px 12px; }
.issues--error { background: #fbeeed; }
.issues--warning { background: #fdf6e7; }
.issues h4 { margin: 0 0 6px; color: #2b3e58; font-size: 12px; font-weight: 800; }
.issues ul, .import-details ul { display: grid; margin: 0; padding: 0; gap: 5px; list-style: none; max-height: 160px; overflow-y: auto; }
.issues li { display: grid; gap: 1px; font-size: 12px; color: #2b3e58; }
.issue-meta { color: #7a879a; font-size: 11px; }
.import-details { color: #65748a; font-size: 12px; }
.import-blocked { margin: 0; color: #a4453a; font-size: 12px; font-weight: 700; }
.import-actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 8px; }
@media (max-width: 620px) { .import-summary { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
</style>
