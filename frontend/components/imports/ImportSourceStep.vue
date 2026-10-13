<script setup lang="ts">
import { computed, ref } from "vue";
import { FileSpreadsheet, FileUp, UploadCloud } from "lucide-vue-next";
import { useImportState } from "~/composables/useImportState";
import { codeNameLabel, toOptions } from "~/utils/selectOptions";
import SearchableSelect from "~/components/ui/SearchableSelect.vue";

/**
 * Passo 1: obra (Unidade → ProjectContext ativo), formato da planilha e um ou
 * mais .xlsx (o Monday exporta um arquivo por grupo/fase ocupada).
 */
const { units, contexts, profiles, selection, files, busy, loadContexts, selectFiles, analyze } = useImportState();

const unitOptions = computed(() => toOptions(units.value));
const contextOptions = computed(() => toOptions(contexts.value, codeNameLabel));
const profileOptions = computed(() =>
  profiles.value.map((item) => ({
    id: item.profileId,
    label: `${item.description || item.profileId} (v${item.version})`,
  })),
);

const canAnalyze = computed(
  () => Boolean(selection.contextId && selection.profileId && files.value.length) && !busy.value,
);
const dragging = ref(false);

function onFiles(event: Event): void {
  const input = event.target as HTMLInputElement;
  selectFiles(Array.from(input.files ?? []));
}

function onDrop(event: DragEvent): void {
  dragging.value = false;
  selectFiles(Array.from(event.dataTransfer?.files ?? []));
}

function size(bytes: number): string {
  return bytes >= 1024 * 1024 ? `${(bytes / (1024 * 1024)).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;
}
</script>

<template>
  <div class="import-step" data-testid="import-step-source">
    <div class="source-layout">
      <section class="import-panel destination" aria-label="Destino da importação">
        <div class="import-panel-head"><h4>Destino</h4></div>
        <div class="field">
          <span>Unidade</span>
          <SearchableSelect
            v-model="selection.unitId"
            :options="unitOptions"
            :clearable="false"
            label="Unidade"
            placeholder="Buscar unidade"
            empty-label="Selecione"
            test-id="import-unit"
            @change="loadContexts()"
          />
        </div>
        <div class="field">
          <span>Obra / contexto de projeto</span>
          <SearchableSelect
            v-model="selection.contextId"
            :options="contextOptions"
            :clearable="false"
            :disabled="!selection.unitId"
            label="Obra / contexto de projeto"
            placeholder="Buscar por código ou nome"
            empty-label="Selecione"
            test-id="import-context"
          />
        </div>
        <p v-if="selection.unitId && contexts.length === 0" class="import-hint" data-testid="import-no-context">
          Nenhuma obra ativa nesta unidade. Cadastre-a em Equipamentos → Administração → Projetos.
        </p>

        <div v-if="profiles.length > 1" class="field">
          <span>Formato da planilha</span>
          <SearchableSelect
            v-model="selection.profileId"
            :options="profileOptions"
            :clearable="false"
            label="Formato da planilha"
            placeholder="Buscar formato"
            empty-label="Selecione"
            test-id="import-profile"
          />
        </div>
        <p v-else-if="profiles.length === 1" class="profile-single" data-testid="import-profile-single">
          <FileSpreadsheet :size="14" aria-hidden="true" />
          Formato da planilha: {{ profiles[0]!.description || profiles[0]!.profileId }}
        </p>
      </section>

      <section class="files" aria-label="Planilhas">
        <label
          class="dropzone"
          :class="{ 'is-dragging': dragging, 'has-files': files.length }"
          @dragover.prevent="dragging = true"
          @dragleave="dragging = false"
          @drop.prevent="onDrop"
        >
          <input
            class="visually-hidden"
            type="file"
            accept=".xlsx"
            multiple
            data-testid="import-file"
            @change="onFiles"
          >
          <UploadCloud :size="26" aria-hidden="true" />
          <strong>Arraste as planilhas aqui ou clique para escolher</strong>
          <span>Arquivos .xlsx exportados do Monday</span>
        </label>
        <p class="import-hint">
          Envie todos os arquivos da obra de uma vez, um por fase com equipamentos. Fases vazias não têm arquivo.
          As planilhas são analisadas no servidor e não ficam armazenadas.
        </p>

        <ul v-if="files.length" class="file-list" data-testid="import-file-list">
          <li v-for="item in files" :key="`${item.name}:${item.size}`">
            <FileSpreadsheet :size="15" aria-hidden="true" />
            <span class="mono">{{ item.name }}</span>
            <small class="mono">{{ size(item.size) }}</small>
          </li>
        </ul>
      </section>
    </div>

    <div class="import-actions">
      <button type="button" class="btn primary" :disabled="!canAnalyze" data-testid="import-analyze" @click="analyze">
        <FileUp :size="15" />
        {{ busy ? "Analisando..." : files.length > 1 ? `Analisar ${files.length} planilhas` : "Analisar planilha" }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.source-layout { display: grid; grid-template-columns: minmax(0, 0.9fr) minmax(0, 1.1fr); gap: 16px; align-items: start; }
.destination { gap: 12px; }
.profile-single { display: flex; align-items: center; gap: 6px; margin: 0; border-radius: 8px; background: var(--wash); padding: 8px 10px; color: var(--ink); font-size: 12px; font-weight: 700; }
.files { display: grid; gap: 10px; }

/* Folha quadriculada: a área de soltar lembra a planilha que ela recebe. */
.dropzone {
  display: grid;
  justify-items: center;
  gap: 4px;
  padding: 30px 18px;
  border: 1.5px dashed #b9c8db;
  border-radius: 14px;
  background-color: #fbfcfe;
  background-image:
    linear-gradient(to right, rgb(48 79 126 / 6%) 1px, transparent 1px),
    linear-gradient(to bottom, rgb(48 79 126 / 6%) 1px, transparent 1px);
  background-size: 56px 22px;
  color: var(--steel);
  text-align: center;
  cursor: pointer;
  transition: border-color 0.15s ease, background-color 0.15s ease;
}
.dropzone strong { color: var(--ink); font-size: 13px; }
.dropzone span { color: var(--muted); font-size: 11.5px; }
.dropzone:hover, .dropzone.is-dragging { border-color: var(--steel); background-color: #f1f6fd; }
.dropzone:focus-within { outline: 2px solid var(--steel); outline-offset: 2px; }
.dropzone.has-files { padding: 18px; }
.visually-hidden { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }

.file-list { display: grid; margin: 0; padding: 0; border: 1px solid var(--rule); border-radius: 12px; list-style: none; overflow: hidden; }
.file-list li { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; align-items: center; gap: 9px; padding: 8px 12px; border-bottom: 1px solid #edf1f6; color: var(--go); }
.file-list li:last-child { border-bottom: 0; }
.file-list span { overflow: hidden; color: var(--ink); font-size: 12px; font-weight: 600; text-overflow: ellipsis; white-space: nowrap; }
.file-list small { color: var(--muted); font-size: 11px; }
@media (max-width: 760px) { .source-layout { grid-template-columns: 1fr; } }
@media (prefers-reduced-motion: reduce) { .dropzone { transition: none; } }
</style>
