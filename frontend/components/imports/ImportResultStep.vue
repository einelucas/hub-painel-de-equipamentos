<script setup lang="ts">
import { useImportState } from "~/composables/useImportState";

/** Passo 5: resultado do apply + reconciliação. Divergência nunca aparece como "sucesso". */
const emit = defineEmits<{ close: [] }>();
const { result } = useImportState();
</script>

<template>
  <div v-if="result" class="import-step" data-testid="import-step-result">
    <p
      class="result-banner"
      :class="result.hasDivergences ? 'result-banner--warn' : 'result-banner--ok'"
      role="status"
      data-testid="import-result-title"
    >
      {{ result.hasDivergences ? "Importação aplicada com divergências" : "Importação concluída" }}
    </p>
    <dl class="result-counts">
      <div><dt>Criados</dt><dd data-testid="result-created">{{ result.created }}</dd></div>
      <div><dt>Atualizados</dt><dd data-testid="result-updated">{{ result.updated }}</dd></div>
      <div><dt>Sem alteração</dt><dd data-testid="result-unchanged">{{ result.unchanged }}</dd></div>
      <div><dt>Divergências</dt><dd data-testid="result-mismatches">{{ result.reconciliation.mismatches }}</dd></div>
    </dl>
    <section v-if="result.reconciliation.divergences.length" class="divergences" data-testid="result-divergences">
      <h4>Divergências encontradas na reconciliação</h4>
      <ul>
        <li v-for="(item, index) in result.reconciliation.divergences" :key="index">
          <strong>{{ item.equipment }}</strong> · {{ item.field }}:
          Hub {{ item.hubValue ?? "vazio" }} / Monday {{ item.sourceValue ?? "vazio" }}
        </li>
      </ul>
    </section>
    <div class="import-actions">
      <button type="button" class="btn primary" data-testid="import-finish" @click="emit('close')">Concluir</button>
    </div>
  </div>
</template>

<style scoped>
.import-step { display: grid; gap: 12px; }
.result-banner { margin: 0; border-radius: 10px; padding: 10px 12px; font-size: 13px; font-weight: 800; }
.result-banner--ok { background: #eaf4e5; color: #477a32; }
.result-banner--warn { background: #fdf6e7; color: #8a5a12; }
.result-counts { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); margin: 0; gap: 8px; }
.result-counts dt { color: #7a879a; font-size: 11px; }
.result-counts dd { margin: 0; color: #2b3e58; font-size: 16px; font-weight: 800; }
.divergences { border-radius: 10px; padding: 9px 12px; background: #fdf6e7; }
.divergences h4 { margin: 0 0 6px; color: #2b3e58; font-size: 12px; font-weight: 800; }
.divergences ul { display: grid; margin: 0; padding: 0; gap: 4px; list-style: none; max-height: 160px; overflow-y: auto; color: #2b3e58; font-size: 12px; }
.import-actions { display: flex; justify-content: flex-end; }
@media (max-width: 620px) { .result-counts { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
</style>
