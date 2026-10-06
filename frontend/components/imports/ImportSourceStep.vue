<script setup lang="ts">
import { computed } from "vue";
import { FileUp } from "lucide-vue-next";
import { useImportState } from "~/composables/useImportState";

/**
 * Passo 1: obra (Unidade → ProjectContext ativo), formato da planilha e um ou
 * mais .xlsx (o Monday exporta um arquivo por grupo/fase ocupada).
 */
const { units, contexts, profiles, selection, files, busy, loadContexts, selectFiles, analyze } = useImportState();

const canAnalyze = computed(
  () => Boolean(selection.contextId && selection.profileId && files.value.length) && !busy.value,
);

function onFiles(event: Event): void {
  const input = event.target as HTMLInputElement;
  selectFiles(Array.from(input.files ?? []));
}

function size(bytes: number): string {
  return bytes >= 1024 * 1024 ? `${(bytes / (1024 * 1024)).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;
}
</script>

<template>
  <div class="import-step" data-testid="import-step-source">
    <div class="import-grid">
      <label class="field">
        <span>Unidade</span>
        <select v-model="selection.unitId" data-testid="import-unit" @change="loadContexts">
          <option value="">Selecione</option>
          <option v-for="unit in units" :key="unit.id" :value="unit.id">{{ unit.name }}</option>
        </select>
      </label>
      <label class="field">
        <span>Obra / contexto de projeto</span>
        <select v-model="selection.contextId" :disabled="!selection.unitId" data-testid="import-context">
          <option value="">Selecione</option>
          <option v-for="item in contexts" :key="item.id" :value="item.id">{{ item.code ? `${item.code} · ${item.name}` : item.name }}</option>
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
      <span>Arquivos exportados do Monday (.xlsx)</span>
      <input type="file" accept=".xlsx" multiple data-testid="import-file" @change="onFiles">
      <small class="import-hint">
        Selecione todos os arquivos da obra de uma vez (um por fase com equipamentos). Fases vazias não têm
        arquivo e não precisam ser enviadas. Os arquivos são analisados no servidor e não são armazenados.
      </small>
    </label>

    <ul v-if="files.length" class="import-files" data-testid="import-file-list">
      <li v-for="item in files" :key="`${item.name}:${item.size}`">
        <span>{{ item.name }}</span><small>{{ size(item.size) }}</small>
      </li>
    </ul>

    <div class="import-actions">
      <button type="button" class="btn primary" :disabled="!canAnalyze" data-testid="import-analyze" @click="analyze">
        <FileUp :size="15" />
        {{ busy ? "Analisando..." : files.length > 1 ? `Analisar ${files.length} planilhas` : "Analisar planilha" }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.import-step { display: grid; gap: 12px; }
.import-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.import-hint { margin: 0; color: #8b96a5; font-size: 11.5px; }
.import-files { display: grid; margin: 0; padding: 0; gap: 4px; list-style: none; max-height: 140px; overflow-y: auto; }
.import-files li { display: flex; justify-content: space-between; gap: 8px; border-radius: 8px; background: #f5f8fb; padding: 5px 9px; color: #2b3e58; font-size: 12px; font-weight: 700; overflow-wrap: anywhere; }
.import-files small { color: #7a879a; font-weight: 600; white-space: nowrap; }
.import-actions { display: flex; justify-content: flex-end; }
@media (max-width: 620px) { .import-grid { grid-template-columns: 1fr; } }
</style>
