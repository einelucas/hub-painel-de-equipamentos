<script setup lang="ts">
import { mdiCheck, mdiClose, mdiPencilOutline, mdiPlus, mdiTrashCanOutline } from "@mdi/js";
import { computed, reactive, ref, useId, watch } from "vue";
import { Search } from "lucide-vue-next";
import type { CatalogList, EapLevel, EapNodeItem } from "~/types/equipment";
import { codeNameLabel, toOptions } from "~/utils/selectOptions";
import SearchableSelect from "~/components/ui/SearchableSelect.vue";
import AppModal from "~/components/ui/AppModal.vue";
import { VBtn } from "vuetify/components";
import { useConfirm } from "~/composables/useConfirm";

const emit = defineEmits<{ changed: [] }>();
const api = useApi();
const { confirm } = useConfirm();

const nodes = ref<EapNodeItem[]>([]);
const loading = ref(false);
const saving = ref(false);
let loadVersion = 0;
const error = ref("");
const formError = ref("");
const creating = ref(false);
const editingId = ref("");
const deletingId = ref("");
const form = reactive<{ code: string; name: string; level: EapLevel; parentId: string; active: boolean }>({
  code: "",
  name: "",
  level: "AREA",
  parentId: "",
  active: true,
});
const formId = `eap-form-${useId()}`;
const formOpen = computed(() => creating.value);
const formTitle = computed(() =>
  editingId.value ? "Editar nó da Árvore EAP" : "Novo nó da Árvore EAP",
);

const levelLabels: Record<EapLevel, string> = {
  ISLAND: "Ilha",
  PROCESS: "Processo",
  AREA: "Área",
};

const levelCounts = computed(() => {
  const counts: Record<EapLevel, number> = { ISLAND: 0, PROCESS: 0, AREA: 0 };
  for (const node of nodes.value) counts[node.level] += 1;
  return counts;
});

const ordered = (items: EapNodeItem[]) =>
  [...items].sort((left, right) => left.code.localeCompare(right.code, "pt-BR", { numeric: true }));

const treeRows = computed(() => {
  const children = new Map<string | null, EapNodeItem[]>();
  for (const node of nodes.value) {
    const key = node.parentId;
    children.set(key, [...(children.get(key) ?? []), node]);
  }
  const rows: { node: EapNodeItem; depth: number }[] = [];
  const visited = new Set<string>();
  const visit = (node: EapNodeItem, depth: number) => {
    if (visited.has(node.id)) return;
    visited.add(node.id);
    rows.push({ node, depth });
    for (const child of ordered(children.get(node.id) ?? [])) visit(child, depth + 1);
  };
  for (const root of ordered(children.get(null) ?? [])) visit(root, 0);
  // Dados antigos inconsistentes continuam visíveis para saneamento, sem sumir da administração.
  for (const orphan of ordered(nodes.value.filter((node) => !visited.has(node.id)))) visit(orphan, 0);
  return rows;
});

const search = ref("");

/**
 * Busca por código ou nome. Mantém os ancestrais de cada nó encontrado para
 * que o resultado continue legível como árvore (Ilha → Processo → Área).
 */
const visibleRows = computed(() => {
  const term = search.value.trim().toLocaleLowerCase("pt-BR");
  if (!term) return treeRows.value;
  const byId = new Map(nodes.value.map((node) => [node.id, node]));
  const keep = new Set<string>();
  for (const node of nodes.value) {
    if (!`${node.code} ${node.name}`.toLocaleLowerCase("pt-BR").includes(term)) continue;
    let current: EapNodeItem | undefined = node;
    while (current && !keep.has(current.id)) {
      keep.add(current.id);
      current = current.parentId ? byId.get(current.parentId) : undefined;
    }
  }
  return treeRows.value.filter((row) => keep.has(row.node.id));
});

const LEVEL_OPTIONS = [
  { id: "ISLAND", label: "Ilha" },
  { id: "PROCESS", label: "Processo" },
  { id: "AREA", label: "Área" },
];

const parentOptions = computed(() => {
  if (form.level === "ISLAND") return [];
  const level: EapLevel = form.level === "AREA" ? "PROCESS" : "ISLAND";
  return ordered(nodes.value.filter((node) => node.level === level && node.active));
});

const parentSelectOptions = computed(() => toOptions(parentOptions.value, codeNameLabel));

async function load(): Promise<void> {
  const version = ++loadVersion;
  loading.value = true;
  error.value = "";
  try {
    const result = (await api.get<CatalogList<EapNodeItem>>("/eap-nodes")).items;
    if (version !== loadVersion) return;
    nodes.value = result;
  } catch (caught) {
    if (version !== loadVersion) return;
    error.value = caught instanceof Error ? caught.message : "Não foi possível carregar a Árvore EAP.";
  } finally {
    if (version === loadVersion) loading.value = false;
  }
}

function startCreate(): void {
  creating.value = true;
  formError.value = "";
  Object.assign(form, {
    code: "",
    name: "",
    level: "AREA" as EapLevel,
    parentId: ordered(nodes.value.filter((node) => node.level === "PROCESS" && node.active))[0]?.id ?? "",
    active: true,
  });
  editingId.value = "";
}

function startEdit(node: EapNodeItem): void {
  creating.value = true;
  editingId.value = node.id;
  formError.value = "";
  Object.assign(form, {
    code: node.code,
    name: node.name,
    level: node.level,
    parentId: node.parentId ?? "",
    active: node.active,
  });
}

function resetForm(): void {
  creating.value = false;
  editingId.value = "";
  formError.value = "";
}

function cancel(): void {
  if (saving.value) return;
  resetForm();
}

async function submit(): Promise<void> {
  if (saving.value) return;
  if (!form.code.trim() || !form.name.trim()) {
    formError.value = "Informe código e nome.";
    return;
  }
  if (form.level === "AREA" && !form.parentId) {
    formError.value = "Selecione o PROCESS pai da área.";
    return;
  }
  saving.value = true;
  formError.value = "";
  try {
    if (editingId.value) {
      await api.patch(`/eap-nodes/${editingId.value}`, {
        name: form.name.trim(),
        active: form.active,
      });
    } else {
      await api.post("/eap-nodes", {
        code: form.code.trim().toUpperCase(),
        name: form.name.trim(),
        level: form.level,
        parentId: form.parentId || null,
      });
    }
    resetForm();
    await load();
    emit("changed");
  } catch (caught) {
    formError.value = caught instanceof Error ? caught.message : "Não foi possível criar o nó EAP.";
  } finally {
    saving.value = false;
  }
}

/** Exclui um nó ainda sem filhos, equipamentos ou vínculos com obras. */
async function remove(node: EapNodeItem): Promise<void> {
  if (saving.value) return;
  const confirmed = await confirm({
    message: `Deseja excluir o nó "${node.code} · ${node.name}"?`,
    detail:
      "Esta ação não pode ser desfeita. Nós com filhos, equipamentos ou vínculos com obras não podem ser excluídos — nesse caso, desative-os.",
  });
  if (!confirmed) return;
  saving.value = true;
  deletingId.value = node.id;
  error.value = "";
  try {
    await api.delete(`/eap-nodes/${node.id}`);
    if (editingId.value === node.id) resetForm();
    await load();
    emit("changed");
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "Não foi possível excluir o nó EAP.";
  } finally {
    saving.value = false;
    deletingId.value = "";
  }
}

watch(
  () => form.level,
  (level) => {
    if (level === "ISLAND") form.parentId = "";
    else if (!parentOptions.value.some((node) => node.id === form.parentId)) {
      form.parentId = parentOptions.value[0]?.id ?? "";
    }
  },
);

void load();
</script>

<template>
  <section class="eap-admin admin-fill" data-testid="eap-tree-admin">
    <header class="eap-header">
      <div>
        <h3>Árvore EAP</h3>
        <p>Catálogo global: Ilha → Processo → Área. Equipamentos usam somente Processo ou Área.</p>
        <p v-if="nodes.length" class="eap-count">
          {{ levelCounts.ISLAND }} ilha{{ levelCounts.ISLAND === 1 ? "" : "s" }} ·
          {{ levelCounts.PROCESS }} processo{{ levelCounts.PROCESS === 1 ? "" : "s" }} ·
          {{ levelCounts.AREA }} área{{ levelCounts.AREA === 1 ? "" : "s" }}
        </p>
      </div>
      <VBtn size="small" variant="tonal" :disabled="saving" data-testid="eap-new" :prepend-icon="mdiPlus" @click="startCreate">
         Novo nó
      </VBtn>
    </header>

    <label v-if="nodes.length" class="eap-search">
      <Search :size="14" aria-hidden="true" />
      <input v-model="search" type="search" placeholder="Buscar por código ou nome" aria-label="Buscar na Árvore EAP">
    </label>

    <p v-if="loading" class="eap-hint"><span class="spinner spinner-small" /> Carregando árvore...</p>
    <p v-else-if="error" class="eap-error" role="alert">{{ error }}</p>
    <p v-else-if="treeRows.length === 0" class="eap-empty" data-testid="eap-empty">
      Nenhum nó EAP cadastrado. Comece por uma Ilha ou Processo.
    </p>
    <p v-else-if="visibleRows.length === 0" class="eap-hint">Nenhum nó corresponde à busca.</p>
    <ul v-else class="eap-tree" role="tree" aria-label="Árvore EAP">
      <li
        v-for="row in visibleRows"
        :key="row.node.id"
        role="treeitem"
        :aria-level="row.depth + 1"
        :class="[`level-${row.node.level.toLowerCase()}`, { inactive: !row.node.active, editing: row.node.id === editingId }]"
        :style="{ '--tree-depth': row.depth }"
        :data-testid="`eap-node-${row.node.id}`"
      >
        <span class="tree-line" aria-hidden="true" />
        <span class="eap-code">{{ row.node.code }}</span>
        <span class="eap-name">{{ row.node.name }}</span>
        <span class="eap-level" :class="`eap-level--${row.node.level.toLowerCase()}`">{{ levelLabels[row.node.level] }}</span>
        <span v-if="!row.node.active" class="eap-inactive">Inativo</span>
        <VBtn
          type="button"
          class="eap-edit"
          :aria-label="`Editar ${row.node.code}`"
          :data-testid="`eap-edit-${row.node.id}`"
          variant="text"
          :icon="mdiPencilOutline"
         @click="startEdit(row.node)">

        </VBtn>
        <VBtn
          type="button"
          class="eap-delete"
          :aria-label="`Excluir ${row.node.code}`"
          :disabled="saving"
          :loading="deletingId === row.node.id"
          :data-testid="`eap-delete-${row.node.id}`"
          variant="tonal" color="error"
          :icon="!(deletingId === row.node.id) ? mdiTrashCanOutline : undefined"
         @click="remove(row.node)">

        </VBtn>
      </li>
    </ul>
  </section>

  <AppModal
    :open="formOpen"
    :title="formTitle"
    :busy="saving"
    @close="cancel"
  >
    <form :id="formId" class="eap-form" data-testid="eap-form" @submit.prevent="submit">
      <div class="field">
        <SearchableSelect
          :model-value="form.level"
          :options="LEVEL_OPTIONS"
          :sorted="false"
          :clearable="false"
          :disabled="Boolean(editingId)"
          label="Nível *"
          placeholder="Buscar nível"
          test-id="eap-level"
          @update:model-value="form.level = $event as EapLevel"
        />
      </div>
      <label class="field">
        <span>Código *</span>
        <input v-model="form.code" maxlength="20" required :disabled="Boolean(editingId)" data-testid="eap-code">
      </label>
      <label class="field eap-name-field">
        <span>Nome *</span>
        <input v-model="form.name" maxlength="160" required data-testid="eap-name">
      </label>
      <div v-if="form.level !== 'ISLAND'" class="field eap-parent-field">
        <SearchableSelect
          v-model="form.parentId"
          :options="parentSelectOptions"
          :clearable="form.level !== 'AREA'"
          :required="form.level === 'AREA'"
          :disabled="Boolean(editingId)"
          :label="form.level === 'AREA' ? 'Processo pai *' : 'Ilha pai (opcional)'"
          placeholder="Buscar por código ou nome"
          :empty-label="form.level === 'AREA' ? 'Selecione' : 'Sem ilha'"
          test-id="eap-parent"
        />
      </div>
      <label v-if="editingId" class="active-check">
        <input v-model="form.active" type="checkbox" data-testid="eap-active">
        Ativo
      </label>
      <p class="eap-help">
        PROCESS usa dois dígitos (ex.: 04). AREA usa processo e sufixo (ex.: 04.A).
        Não informe prefixo da unidade ou da obra.
      </p>
      <p v-if="formError" class="eap-error" role="alert">{{ formError }}</p>
    </form>

    <template #actions>
      <VBtn size="small" variant="outlined" :disabled="saving" :prepend-icon="mdiClose" @click="cancel">
         Cancelar
      </VBtn>
      <VBtn
        type="submit"
        size="small"
        variant="tonal"
        :form="formId"
        :loading="saving"
        data-testid="eap-save"
       :prepend-icon="!saving ? mdiCheck : undefined" :disabled="saving">

        {{ saving ? "Salvando..." : "Salvar" }}
      </VBtn>
    </template>
  </AppModal>
</template>

<style scoped>
/* Cabeçalho e busca ficam parados; só a árvore rola (dentro do painel). */
.eap-admin { display: flex; flex-direction: column; gap: 12px; }
.eap-admin > * { flex: 0 0 auto; }
.eap-search { display: flex; align-items: center; gap: 8px; border: 1px solid var(--rule, #dde5ef); border-radius: 9px; padding: 0 10px; background: #fff; color: var(--muted, #6b7a8f); }
.eap-search:focus-within { border-color: var(--steel, #304f7e); box-shadow: 0 0 0 2px rgb(48 79 126 / 12%); }
.eap-search input { min-width: 0; flex: 1; border: 0; outline: 0; padding: 8px 0; background: transparent; color: var(--ink, #1f3352); font-size: 12.5px; }
.eap-header { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; padding-bottom: 10px; border-bottom: 1px solid var(--rule, #dde5ef); }
.eap-header h3 { margin: 0; color: var(--ink, #1f3352); font-size: 17px; font-weight: 800; letter-spacing: -0.01em; }
.eap-header p { margin: 3px 0 0; color: var(--muted, #6b7a8f); font-size: 12px; }
.eap-count { margin-top: 4px !important; font-family: var(--mono, monospace); font-size: 11px !important; }

.eap-form { display: grid; grid-template-columns: minmax(110px, .7fr) minmax(130px, .8fr) minmax(180px, 1.5fr); gap: 14px 16px; }
.eap-parent-field { grid-column: 1 / span 2; }
.eap-help { grid-column: 1 / -1; margin: 0; color: var(--muted, #6b7a8f); font-size: 11.5px; }
.eap-error { grid-column: 1 / -1; margin: 0; color: var(--stop, #a4453a); font-size: 12px; font-weight: 700; }
.eap-hint { display: flex; align-items: center; gap: 8px; margin: 0; color: var(--muted, #6b7a8f); font-size: 12px; }
.eap-empty { margin: 0; border: 1px dashed var(--rule, #dde5ef); border-radius: 12px; padding: 22px; color: var(--muted, #6b7a8f); font-size: 12.5px; text-align: center; }

/* Árvore: cada nível com peso próprio — Ilha é cabeçalho, Área é folha. */
.eap-tree { display: block; margin: 0; padding: 6px 0; border: 1px solid var(--rule, #dde5ef); border-radius: 12px; background: #fff; list-style: none; overflow-y: auto; overscroll-behavior: contain; }
.eap-admin > .eap-tree { min-height: 0; flex: 0 1 auto; }
.eap-tree li {
  position: relative;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto auto auto auto;
  align-items: center;
  gap: 10px;
  min-height: 36px;
  padding: 4px 10px 4px calc(16px + var(--tree-depth) * 24px);
  color: var(--ink, #1f3352);
}
.eap-tree li:hover { background: #fafcfe; }
.eap-tree li.editing { background: #f1f6fd; }
/* guias verticais: uma por nível acima do nó */
.tree-line {
  position: absolute;
  top: 0;
  bottom: 0;
  left: 18px;
  width: calc(var(--tree-depth) * 24px);
  background-image: linear-gradient(to right, var(--rule, #dde5ef) 1px, transparent 1px);
  background-size: 24px 100%;
  pointer-events: none;
}
.eap-code { min-width: 44px; color: var(--steel, #304f7e); font-family: var(--mono, monospace); font-size: 12px; font-weight: 700; }
.eap-name { overflow: hidden; font-size: 12.5px; font-weight: 600; text-overflow: ellipsis; white-space: nowrap; }
.level-island .eap-name { font-size: 13px; font-weight: 800; }
.level-island .eap-code { color: var(--ink, #1f3352); }
.level-process .eap-name { font-weight: 700; }
.eap-level, .eap-inactive { border-radius: 6px; padding: 2px 7px; font-size: 10px; font-weight: 800; letter-spacing: 0.02em; }
.eap-level--island { background: var(--ink, #1f3352); color: #fff; }
.eap-level--process { background: #e3ecf8; color: var(--steel, #304f7e); }
.eap-level--area { background: #f1f4f8; color: var(--muted, #6b7a8f); }
.eap-inactive { background: var(--stop-wash, #fbeeed); color: var(--stop, #a4453a); }
.eap-tree li.inactive .eap-name, .eap-tree li.inactive .eap-code { color: #9aa6b5; }
.active-check { display: flex; align-items: center; gap: 7px; color: #526176; font-size: 12px; font-weight: 700; }
@media (max-width: 700px) {
  .eap-form { grid-template-columns: 1fr; }
  .eap-parent-field { grid-column: auto; }
  .eap-tree li { grid-template-columns: auto minmax(90px, 1fr) auto; padding-left: calc(12px + var(--tree-depth) * 14px); }
  .tree-line { display: none; }
  .eap-inactive { grid-column: 2; justify-self: start; }
}
</style>
