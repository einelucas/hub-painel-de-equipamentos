<script setup lang="ts">
import { computed } from "vue";
import { FileUp } from "lucide-vue-next";
import { useImportState } from "~/composables/useImportState";

/** Passo 1: obra (Unidade → ProjectContext ativo), formato da planilha e arquivo .xlsx. */
const { units, contexts, profiles, selection, file, busy, loadContexts, selectFile, analyze } = useImportState();

const canAnalyze = computed(
  () => Boolean(selection.contextId && selection.profileId && file.value) && !busy.value,
);

function onFile(event: Event): void {
  const input = event.target as HTMLInputElement;
  selectFile(input.files?.[0] ?? null);
}
</script>

<template>
  <div class="import-step" data-testid="import-step-source">
    <div class="import-grid">
      <label class="field">
        <span>Unidade</span>
        <select v-model="selection.unitId" data-testid="import-unit" @change="loadContexts">
          <option value="">Selecione</option>
          <option v-for="unit in units" :key="unit.id" :value="unit.id">{{ unit.code }} · {{ unit.name }}</option>
        </select>
      </label>
      <label class="field">
        <span>Obra / contexto de projeto</span>
        <select v-model="selection.contextId" :disabled="!selection.unitId" data-testid="import-context">
          <option value="">Selecione</option>
          <option v-for="item in contexts" :key="item.id" :value="item.id">{{ item.code }} · {{ item.name }}</option>
        </select>
      </label>
    </div>
    <p v-if="selection.unitId && contexts.length === 0" class="import-hint" data-testid="import-no-context">
      Nenhuma obra ativa nesta unidade. Cadastre-a em Equipamentos → Administração → Projetos.
    </p>

    <label v-if="profiles.length > 1" class="field">
      <span>Formato da planilha</span>
      <select v-model="selection.profileId" data-testid="import-profile">
        <option value="">Selecione</option>
        <option v-for="item in profiles" :key="item.profileId" :value="item.profileId">
          {{ item.description || item.profileId }} (v{{ item.version }})
        </option>
      </select>
    </label>
    <p v-else-if="profiles.length === 1" class="import-hint" data-testid="import-profile-single">
      Formato da planilha: {{ profiles[0]!.description || profiles[0]!.profileId }}
    </p>

    <label class="import-file field">
      <span>Arquivo exportado do Monday (.xlsx)</span>
      <input type="file" accept=".xlsx" data-testid="import-file" @change="onFile">
      <small class="import-hint">O arquivo é analisado no servidor e não é armazenado.</small>
    </label>

    <div class="import-actions">
      <button type="button" class="btn primary" :disabled="!canAnalyze" data-testid="import-analyze" @click="analyze">
        <FileUp :size="15" /> {{ busy ? "Analisando..." : "Analisar planilha" }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.import-step { display: grid; gap: 12px; }
.import-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.import-hint { margin: 0; color: #8b96a5; font-size: 11.5px; }
.import-actions { display: flex; justify-content: flex-end; }
@media (max-width: 620px) { .import-grid { grid-template-columns: 1fr; } }
</style>
