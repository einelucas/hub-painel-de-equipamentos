<script setup lang="ts">
import { VBtn } from "vuetify/components";
import { useImportState } from "~/composables/useImportState";

/** Passo 5: resultado do apply + reconciliação. Divergência nunca aparece como "sucesso". */
const emit = defineEmits<{ close: [] }>();
const { result } = useImportState();
</script>

<template>
  <div v-if="result" class="import-step" data-testid="import-step-result">
    <VAlert
      :type="result.hasDivergences ? 'warning' : 'success'"
      role="status"
    >
      <template #title>
        <span data-testid="import-result-title">
          {{ result.hasDivergences ? "Importação aplicada com divergências" : "Importação concluída" }}
        </span>
      </template>
      {{
        result.hasDivergences
          ? "Os valores abaixo ficaram diferentes entre o Hub e o Monday. Revise-os nos equipamentos."
          : "O Hub confere com as planilhas enviadas."
      }}
    </VAlert>
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
      <VBtn variant="flat" color="success" data-testid="import-finish" @click="emit('close')">Concluir</VBtn>
    </div>
  </div>
</template>

<style scoped>
.divergences { display: grid; gap: 8px; border-left: 3px solid #d4a24c; border-radius: 10px; padding: 11px 14px; background: var(--caution-wash); }
.divergences h4 { margin: 0; color: var(--ink); font-size: 12.5px; font-weight: 800; }
.divergences ul { display: grid; margin: 0; padding: 0; gap: 5px; list-style: none; max-height: 220px; overflow-y: auto; color: var(--ink); font-size: 12px; }
</style>
