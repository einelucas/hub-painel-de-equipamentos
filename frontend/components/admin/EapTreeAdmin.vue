<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";
import { Check, Plus, X } from "lucide-vue-next";
import type { CatalogList, EapLevel, EapNodeItem } from "~/types/equipment";

const emit = defineEmits<{ changed: [] }>();
const api = useApi();

const nodes = ref<EapNodeItem[]>([]);
const loading = ref(false);
const saving = ref(false);
const error = ref("");
const formError = ref("");
const creating = ref(false);
const form = reactive<{ code: string; name: string; level: EapLevel; parentId: string }>({
  code: "",
  name: "",
  level: "AREA",
  parentId: "",
});

const levelLabels: Record<EapLevel, string> = {
  ISLAND: "Ilha",
  PROCESS: "Processo",
  AREA: "Área",
};

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

const parentOptions = computed(() => {
  if (form.level === "ISLAND") return [];
  const level: EapLevel = form.level === "AREA" ? "PROCESS" : "ISLAND";
  return ordered(nodes.value.filter((node) => node.level === level && node.active));
});

async function load(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    nodes.value = (await api.get<CatalogList<EapNodeItem>>("/eap-nodes")).items;
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "Não foi possível carregar a Árvore EAP.";
  } finally {
    loading.value = false;
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
  });
}

function cancel(): void {
  creating.value = false;
  formError.value = "";
}

async function submit(): Promise<void> {
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
    await api.post("/eap-nodes", {
      code: form.code.trim().toUpperCase(),
      name: form.name.trim(),
      level: form.level,
      parentId: form.parentId || null,
    });
    cancel();
    await load();
    emit("changed");
  } catch (caught) {
    formError.value = caught instanceof Error ? caught.message : "Não foi possível criar o nó EAP.";
  } finally {
    saving.value = false;
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
  <section class="eap-admin" data-testid="eap-tree-admin">
    <header class="eap-header">
      <div>
        <h3>Árvore EAP</h3>
        <p>Catálogo global: Ilha → Processo → Área. Equipamentos usam somente Processo ou Área.</p>
      </div>
      <button type="button" class="btn small" :disabled="saving" data-testid="eap-new" @click="startCreate">
        <Plus :size="14" /> Novo nó
      </button>
    </header>

    <form v-if="creating" class="eap-form" data-testid="eap-form" @submit.prevent="submit">
      <label class="field">
        <span>Nível *</span>
        <select v-model="form.level" data-testid="eap-level">
          <option value="ISLAND">Ilha</option>
          <option value="PROCESS">Processo</option>
          <option value="AREA">Área</option>
        </select>
      </label>
      <label class="field">
        <span>Código *</span>
        <input v-model="form.code" maxlength="20" required data-testid="eap-code">
      </label>
      <label class="field eap-name-field">
        <span>Nome *</span>
        <input v-model="form.name" maxlength="160" required data-testid="eap-name">
      </label>
      <label v-if="form.level !== 'ISLAND'" class="field eap-parent-field">
        <span>{{ form.level === "AREA" ? "Processo pai *" : "Ilha pai (opcional)" }}</span>
        <select v-model="form.parentId" :required="form.level === 'AREA'" data-testid="eap-parent">
          <option value="">{{ form.level === "AREA" ? "Selecione" : "Sem ilha" }}</option>
          <option v-for="node in parentOptions" :key="node.id" :value="node.id">
            {{ node.code }} · {{ node.name }}
          </option>
        </select>
      </label>
      <p class="eap-help">
        PROCESS usa dois dígitos (ex.: 04). AREA usa processo e sufixo (ex.: 04.A).
        Não informe prefixo da unidade ou da obra.
      </p>
      <p v-if="formError" class="eap-error" role="alert">{{ formError }}</p>
      <div class="eap-form-actions">
        <button type="button" class="btn small" @click="cancel"><X :size="13" /> Cancelar</button>
        <button type="submit" class="btn small primary" :disabled="saving" data-testid="eap-save">
          <Check :size="13" /> {{ saving ? "Salvando..." : "Salvar" }}
        </button>
      </div>
    </form>

    <p v-if="loading" class="eap-hint"><span class="spinner spinner-small" /> Carregando árvore...</p>
    <p v-else-if="error" class="eap-error" role="alert">{{ error }}</p>
    <p v-else-if="treeRows.length === 0" class="eap-hint" data-testid="eap-empty">
      Nenhum nó EAP cadastrado. Comece por uma Ilha ou Processo.
    </p>
    <ul v-else class="eap-tree" role="tree" aria-label="Árvore EAP">
      <li
        v-for="row in treeRows"
        :key="row.node.id"
        role="treeitem"
        :aria-level="row.depth + 1"
        :style="{ '--tree-depth': row.depth }"
        :data-testid="`eap-node-${row.node.id}`"
      >
        <span class="tree-line" aria-hidden="true" />
        <span class="eap-code">{{ row.node.code }}</span>
        <span class="eap-name">{{ row.node.name }}</span>
        <span class="eap-level">{{ levelLabels[row.node.level] }}</span>
        <span v-if="!row.node.active" class="eap-inactive">Inativo</span>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.eap-admin { display: grid; gap: 12px; padding: 4px 0 14px; }
.eap-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.eap-header h3 { margin: 0; color: #2b3e58; font-size: 13px; font-weight: 800; }
.eap-header p { margin: 3px 0 0; color: #7a879a; font-size: 11.5px; }
.eap-form { display: grid; grid-template-columns: minmax(110px, .7fr) minmax(130px, .8fr) minmax(180px, 1.5fr); gap: 10px; border: 1px solid #dce5f0; border-radius: 10px; padding: 12px; background: #f8fafc; }
.eap-parent-field { grid-column: 1 / span 2; }
.eap-help { grid-column: 1 / -1; margin: 0; color: #7a879a; font-size: 11px; }
.eap-error { grid-column: 1 / -1; margin: 0; color: #a4453a; font-size: 12px; font-weight: 700; }
.eap-form-actions { display: flex; grid-column: 1 / -1; justify-content: flex-end; gap: 8px; }
.eap-hint { display: flex; align-items: center; gap: 8px; margin: 0; color: #8b96a5; font-size: 12px; }
.eap-tree { display: grid; margin: 0; padding: 2px 0; list-style: none; }
.eap-tree li { position: relative; display: grid; grid-template-columns: auto minmax(120px, 1fr) auto auto; align-items: center; gap: 8px; min-height: 34px; margin-left: calc(var(--tree-depth) * 22px); border-bottom: 1px solid #f0f3f7; padding: 5px 3px 5px 15px; color: #2b3e58; }
.tree-line { position: absolute; top: 0; bottom: 0; left: 3px; width: 8px; border-bottom: 1px solid #cbd6e4; border-left: 1px solid #cbd6e4; }
.eap-code { border-radius: 5px; background: #e9f1fb; padding: 2px 6px; color: #294b77; font-size: 10.5px; font-weight: 800; }
.eap-name { overflow: hidden; font-size: 12.5px; font-weight: 700; text-overflow: ellipsis; white-space: nowrap; }
.eap-level, .eap-inactive { border-radius: 999px; padding: 3px 7px; font-size: 10px; font-weight: 750; }
.eap-level { background: #eef2f7; color: #627086; }
.eap-inactive { background: #f5e9e7; color: #925147; }
.spinner-small { width: 14px; height: 14px; border-width: 2px; }
@media (max-width: 700px) {
  .eap-form { grid-template-columns: 1fr; }
  .eap-parent-field { grid-column: auto; }
  .eap-tree li { grid-template-columns: auto minmax(90px, 1fr) auto; }
  .eap-inactive { grid-column: 2; justify-self: start; }
}
</style>
