<script setup lang="ts">
import { AlertTriangle, CheckCircle2 } from "lucide-vue-next";
import { useImportState } from "~/composables/useImportState";

/** Passo 5: resultado do apply + reconciliação. Divergência nunca aparece como "sucesso". */
const emit = defineEmits<{ close: [] }>();
const { result } = useImportState();
</script>

<template>
  <div v-if="result" class="import-step" data-testid="import-step-result">
    <div class="result-banner" :class="result.hasDivergences ? 'result-banner--warn' : 'result-banner--ok'">
      <AlertTriangle v-if="result.hasDivergences" :size="22" aria-hidden="true" />
      <CheckCircle2 v-else :size="22" aria-hidden="true" />
      <div>
        <p role="status" data-testid="import-result-title">
          {{ result.hasDivergences ? "Importação aplicada com divergências" : "Importação concluída" }}
        </p>
        <small>
          {{
            result.hasDivergences
              ? "Os valores abaixo ficaram diferentes entre o Hub e o Monday. Revise-os nos equipamentos."
              : "O Hub confere com as planilhas enviadas."
          }}
        </small>
      </div>
    </div>
    <dl class="import-ledger">
      <div class="is-go"><dt>Criados</dt><dd data-testid="result-created">{{ result.created }}</dd></div>
      <div><dt>Atualizados</dt><dd data-testid="result-updated">{{ result.updated }}</dd></div>
      <div><dt>Sem alteração</dt><dd data-testid="result-unchanged">{{ result.unchanged }}</dd></div>
      <div :class="{ 'is-caution': result.reconciliation.mismatches > 0 }">
        <dt>Divergências</dt><dd data-testid="result-mismatches">{{ result.reconciliation.mismatches }}</dd>
      </div>
    </dl>
    <section v-if="result.reconciliation.divergences.length" class="divergences" data-testid="result-divergences">
      <h4>Divergências encontradas na reconciliação</h4>
      <ul>
        <li v-for="(item, index) in result.reconciliation.divergences" :key="index">
          <strong>{{ item.equipment }}</strong> · {{ item.field }}:
          Hub <span class="mono">{{ item.hubValue ?? "vazio" }}</span> / Monday <span class="mono">{{ item.sourceValue ?? "vazio" }}</span>
        </li>
      </ul>
    </section>
    <div class="import-actions">
      <button type="button" class="btn primary" data-testid="import-finish" @click="emit('close')">Concluir</button>
    </div>
  </div>
</template>

<style scoped>
.result-banner { display: flex; align-items: flex-start; gap: 12px; border-radius: 12px; padding: 14px 16px; }
.result-banner p { margin: 0; font-size: 15px; font-weight: 800; }
.result-banner small { color: inherit; font-size: 12px; opacity: 0.85; }
.result-banner--ok { background: var(--go-wash); color: var(--go); }
.result-banner--warn { background: var(--caution-wash); color: var(--caution); }
.divergences { display: grid; gap: 8px; border-left: 3px solid #d4a24c; border-radius: 10px; padding: 11px 14px; background: var(--caution-wash); }
.divergences h4 { margin: 0; color: var(--ink); font-size: 12.5px; font-weight: 800; }
.divergences ul { display: grid; margin: 0; padding: 0; gap: 5px; list-style: none; max-height: 220px; overflow-y: auto; color: var(--ink); font-size: 12px; }
</style>
