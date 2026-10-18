<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";
import { Check, Pencil, Plus, Search, X } from "lucide-vue-next";
import type { CatalogItem, CatalogList } from "~/types/equipment";
import { catalogColor } from "~/utils/catalogColors";

/**
 * CRUD de um catálogo (sem exclusão física — desativar é o caminho).
 * As cinco entidades usam este mesmo componente; só mudam rota e campos.
 */
const props = defineProps<{
  /** Rota base do catálogo, ex.: "/areas" ou "/units". */
  path: string;
  label: string;
  /** Campos extras enviados na criação, ex.: { unitId }. */
  parent?: Record<string, string>;
  /** Query da listagem, ex.: { unit_id }. */
  query?: Record<string, string>;
  hasCode: boolean;
  /** Cor hexadecimal usada por badges do catálogo. */
  hasColor?: boolean;
  /** Campo de significado/descrição, usado atualmente por Work Packages. */
  hasDescription?: boolean;
  /** Mensagem quando falta selecionar o pai (unidade/contexto). */
  requiresParent?: string;
  /**
   * Rota base de edição (PATCH), quando difere da listagem. Contextos são
   * listados em "/units/{id}/project-contexts" mas editados em "/project-contexts/{id}".
   */
  itemPath?: string;
}>();
const emit = defineEmits<{ changed: [] }>();

const api = useApi();
const items = ref<CatalogItem[]>([]);
const loading = ref(false);
const saving = ref(false);
const togglingId = ref<string | null>(null);
let loadVersion = 0;
const error = ref("");
const formError = ref("");
const editingId = ref<string | null>(null);
const creating = ref(false);
const form = reactive({ name: "", code: "", description: "", color: "#777ae5" });
const search = ref("");

const activeCount = computed(() => items.value.filter((item) => item.active).length);
const inactiveCount = computed(() => items.value.length - activeCount.value);
const visibleItems = computed(() => {
  const term = search.value.trim().toLocaleLowerCase("pt-BR");
  if (!term) return items.value;
  return items.value.filter((item) =>
    [item.code, item.name, item.description]
      .filter(Boolean)
      .some((value) => String(value).toLocaleLowerCase("pt-BR").includes(term)),
  );
});

const blocked = computed(() => Boolean(props.requiresParent));

async function load(): Promise<void> {
  const version = ++loadVersion;
  if (blocked.value) {
    items.value = [];
    loading.value = false;
    return;
  }
  loading.value = true;
  error.value = "";
  try {
    // Visão administrativa: inclui inativos para permitir reativar (exige catalogs:manage).
    const result = (
      await api.get<CatalogList<CatalogItem>>(props.path, { ...props.query, include_inactive: "true" })
    ).items;
    if (version !== loadVersion) return;
    items.value = result;
  } catch (caught) {
    if (version !== loadVersion) return;
    error.value = caught instanceof Error ? caught.message : `Não foi possível carregar ${props.label}.`;
  } finally {
    if (version === loadVersion) loading.value = false;
  }
}

function startCreate(): void {
  creating.value = true;
  editingId.value = null;
  formError.value = "";
  form.name = "";
  form.code = "";
  form.description = "";
  form.color = "#777ae5";
}

function startEdit(item: CatalogItem): void {
  creating.value = false;
  editingId.value = item.id;
  formError.value = "";
  form.name = item.name;
  form.code = item.code ?? "";
  form.description = item.description ?? "";
  form.color = item.color ?? "#777ae5";
}

function cancel(): void {
  creating.value = false;
  editingId.value = null;
  formError.value = "";
}

async function submit(): Promise<void> {
  if (saving.value) return;
  if (!form.name.trim() || (props.hasCode && !form.code.trim())) {
    formError.value = props.hasCode ? "Informe código e nome." : "Informe o nome.";
    return;
  }
  saving.value = true;
  formError.value = "";
  const payload: Record<string, unknown> = { name: form.name.trim() };
  if (props.hasCode) payload.code = form.code.trim();
  if (props.hasDescription) payload.description = form.description.trim() || null;
  if (props.hasColor) payload.color = form.color;
  try {
    if (editingId.value) await api.patch(`${props.itemPath ?? props.path}/${editingId.value}`, payload);
    else await api.post(props.path, { ...payload, ...(props.parent ?? {}) });
    cancel();
    await load();
    emit("changed");
  } catch (caught) {
    formError.value = caught instanceof Error ? caught.message : "Não foi possível salvar.";
  } finally {
    saving.value = false;
  }
}

/** Desativar some com o item das listas operacionais, por isso confirmamos. */
async function toggleActive(item: CatalogItem): Promise<void> {
  if (saving.value) return;
  if (item.active && !confirm(`Desativar "${item.name}"? Ele deixa de aparecer nos formulários.`)) {
    return;
  }
  saving.value = true;
  togglingId.value = item.id;
  error.value = "";
  try {
    await api.patch(`${props.itemPath ?? props.path}/${item.id}`, { active: !item.active });
    await load();
    emit("changed");
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "Não foi possível alterar a situação.";
  } finally {
    saving.value = false;
    togglingId.value = null;
  }
}

watch(
  () => [props.path, props.query, props.requiresParent],
  () => {
    search.value = "";
    void load();
  },
  { deep: true, immediate: true },
);
</script>

<template>
  <section class="catalog admin-fill" :data-testid="`catalog-${props.label.toLowerCase()}`">
    <header class="catalog-header">
      <div>
        <h3>{{ props.label }}</h3>
        <p v-if="!blocked && !loading && items.length" class="catalog-count">
          {{ activeCount }} ativo{{ activeCount === 1 ? "" : "s" }}<template v-if="inactiveCount"> · {{ inactiveCount }} inativo{{ inactiveCount === 1 ? "" : "s" }}</template>
        </p>
      </div>
      <button v-if="!blocked" type="button" class="btn small primary" :disabled="saving" @click="startCreate">
        <Plus :size="14" /> Novo
      </button>
    </header>

    <p v-if="blocked" class="catalog-hint" data-testid="catalog-blocked">{{ props.requiresParent }}</p>
    <template v-else>
      <form v-if="creating || editingId" class="catalog-form" @submit.prevent="submit">
        <p class="catalog-form-title">{{ editingId ? "Editar registro" : `Novo registro em ${props.label}` }}</p>
        <label v-if="props.hasCode" class="field"><span>Código *</span><input v-model="form.code" maxlength="60" required></label>
        <label class="field" :class="{ 'full': !props.hasCode }"><span>Nome *</span><input v-model="form.name" maxlength="200" required></label>
        <label v-if="props.hasColor" class="field color-field">
          <span>Cor *</span>
          <span class="color-control"><input v-model="form.color" type="color" required><code>{{ form.color }}</code></span>
        </label>
        <label v-if="props.hasDescription" class="field description-field">
          <span>Descrição</span>
          <textarea
            v-model="form.description"
            maxlength="500"
            rows="3"
            placeholder="Significado da WP; deixe vazio enquanto não estiver documentado."
          />
        </label>
        <p v-if="formError" class="catalog-error" role="alert">{{ formError }}</p>
        <div class="catalog-form-actions">
          <button type="button" class="btn small" @click="cancel"><X :size="13" /> Cancelar</button>
          <button type="submit" class="btn small primary" :disabled="saving" :aria-busy="saving">
            <span v-if="saving" class="spinner-small" aria-hidden="true" /><Check v-else :size="13" /> {{ saving ? "Salvando..." : "Salvar" }}
          </button>
        </div>
      </form>

      <label v-if="items.length" class="catalog-search">
        <Search :size="14" aria-hidden="true" />
        <input v-model="search" type="search" :placeholder="`Buscar em ${props.label}`" :aria-label="`Buscar em ${props.label}`">
      </label>

      <p v-if="loading" class="catalog-hint"><span class="spinner spinner-small" /> Carregando...</p>
      <p v-else-if="error" class="catalog-error" role="alert">{{ error }}</p>
      <p v-else-if="items.length === 0" class="catalog-empty" data-testid="catalog-empty">
        Nenhum registro cadastrado. Use "Novo" para criar o primeiro.
      </p>
      <p v-else-if="visibleItems.length === 0" class="catalog-hint">Nenhum registro corresponde à busca.</p>
      <ul v-else class="catalog-list">
        <li
          v-for="item in visibleItems"
          :key="item.id"
          :class="{ inactive: !item.active, editing: item.id === editingId, 'no-code': !props.hasCode, 'has-swatch': props.hasColor }"
          :data-testid="`catalog-item-${item.id}`"
        >
          <span v-if="props.hasColor" class="catalog-swatch" :style="{ backgroundColor: catalogColor(item.color) }" aria-hidden="true" />
          <span v-if="props.hasCode" class="catalog-code">{{ item.code ?? "—" }}</span>
          <span class="catalog-name">
            <strong>{{ item.name }}</strong>
            <small v-if="props.hasDescription" :class="{ missing: !item.description?.trim() }">
              {{ item.description?.trim() || "WP sem descrição" }}
            </small>
          </span>
          <span class="status" :class="item.active ? 'status--on' : 'status--off'">
            {{ item.active ? "Ativo" : "Inativo" }}
          </span>
          <span class="catalog-actions">
            <button type="button" class="text-button" :disabled="saving" @click="startEdit(item)">
              <Pencil :size="12" /> Editar
            </button>
            <button type="button" class="text-button" :class="{ 'text-button--quiet': item.active }" :disabled="saving" :aria-busy="togglingId === item.id" @click="toggleActive(item)">
              <span v-if="togglingId === item.id" class="spinner-small" aria-hidden="true" />
              {{ togglingId === item.id ? "Salvando..." : item.active ? "Desativar" : "Reativar" }}
            </button>
          </span>
        </li>
      </ul>
    </template>
  </section>
</template>

<style scoped>
/* Cabeçalho, formulário e busca ficam parados; só a lista rola (dentro do painel). */
.catalog { display: flex; flex-direction: column; gap: 12px; }
.catalog > * { flex: 0 0 auto; }
.catalog-header { display: flex; align-items: flex-end; justify-content: space-between; gap: 12px; padding-bottom: 10px; border-bottom: 1px solid var(--rule, #dde5ef); }
.catalog-header h3 { margin: 0; color: var(--ink, #1f3352); font-size: 17px; font-weight: 800; letter-spacing: -0.01em; }
.catalog-count { margin: 2px 0 0; color: var(--muted, #6b7a8f); font-family: var(--mono, monospace); font-size: 11px; }
.catalog-hint { display: flex; align-items: center; gap: 8px; margin: 0; color: var(--muted, #6b7a8f); font-size: 12px; }
.catalog-empty { margin: 0; border: 1px dashed var(--rule, #dde5ef); border-radius: 12px; padding: 22px; color: var(--muted, #6b7a8f); font-size: 12.5px; text-align: center; }
.catalog-error { margin: 0; color: var(--stop, #a4453a); font-size: 12px; font-weight: 700; }

.catalog-form { display: grid; grid-template-columns: minmax(0, 0.6fr) minmax(0, 1.4fr); gap: 10px 12px; border: 1px solid #c9d8ec; border-radius: 12px; padding: 14px; background: var(--wash, #f3f6fb); }
.catalog-form-title { grid-column: 1 / -1; margin: 0; color: var(--ink, #1f3352); font-size: 12.5px; font-weight: 800; }
.catalog-form .full { grid-column: 1 / -1; }
.description-field, .color-field { grid-column: 1 / -1; }
.color-control { display: flex; align-items: center; gap: 10px; }
.color-control input { width: 44px; height: 34px; border: 1px solid var(--rule, #dde5ef); border-radius: 8px; padding: 3px; background: #fff; cursor: pointer; }
.color-control code { color: var(--muted, #6b7a8f); font-size: 12px; text-transform: uppercase; }
.description-field textarea { min-height: 72px; resize: vertical; }
.catalog-form .catalog-error { grid-column: 1 / -1; }
.catalog-form-actions { display: flex; grid-column: 1 / -1; justify-content: flex-end; gap: 8px; }

.catalog-search { display: flex; align-items: center; gap: 8px; border: 1px solid var(--rule, #dde5ef); border-radius: 9px; padding: 0 10px; background: #fff; color: var(--muted, #6b7a8f); }
.catalog-search:focus-within { border-color: var(--steel, #304f7e); box-shadow: 0 0 0 2px rgb(48 79 126 / 12%); }
.catalog-search input { min-width: 0; flex: 1; border: 0; outline: 0; padding: 8px 0; background: transparent; color: var(--ink, #1f3352); font-size: 12.5px; }

/* Encolhe até caber no painel, mas não estica: lista curta continua curta. */
.catalog > .catalog-list { min-height: 0; flex: 0 1 auto; }
.catalog-list { display: block; margin: 0; padding: 0; border: 1px solid var(--rule, #dde5ef); border-radius: 12px; list-style: none; overflow-y: auto; overscroll-behavior: contain; }
.catalog-list li {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto auto;
  align-items: center;
  gap: 12px;
  padding: 9px 14px;
  border-bottom: 1px solid #edf1f6;
  background: #fff;
}
.catalog-list li.no-code { grid-template-columns: minmax(0, 1fr) auto auto; }
.catalog-list li.has-swatch { grid-template-columns: auto auto minmax(0, 1fr) auto auto; }
.catalog-list li.no-code.has-swatch { grid-template-columns: auto minmax(0, 1fr) auto auto; }
.catalog-list li:last-child { border-bottom: 0; }
.catalog-list li:hover { background: #fafcfe; }
.catalog-list li.editing { background: #f1f6fd; }
.catalog-list li.inactive .catalog-name strong, .catalog-list li.inactive .catalog-code { color: #9aa6b5; }
.catalog-code { min-width: 64px; color: var(--steel, #304f7e); font-family: var(--mono, monospace); font-size: 12px; font-weight: 700; }
.catalog-swatch { width: 14px; height: 14px; border: 2px solid rgb(255 255 255 / 75%); border-radius: 999px; box-shadow: 0 0 0 1px #d5deea; }
.catalog-name { display: grid; min-width: 0; gap: 1px; }
.catalog-name strong { overflow: hidden; color: var(--ink, #1f3352); font-size: 12.5px; font-weight: 700; text-overflow: ellipsis; white-space: nowrap; }
.catalog-name small { overflow: hidden; color: var(--muted, #6b7a8f); font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
.catalog-name small.missing { color: #a3adbb; font-style: italic; }
.status { display: inline-flex; align-items: center; gap: 5px; font-size: 11px; font-weight: 750; }
.status::before { width: 7px; height: 7px; border-radius: 999px; background: currentColor; content: ""; }
.status--on { color: var(--go, #3f7a2e); }
.status--off { color: #9aa6b5; }
.catalog-actions { display: flex; align-items: center; gap: 12px; }
.text-button { display: inline-flex; align-items: center; gap: 4px; border: 0; padding: 2px; background: transparent; color: var(--steel, #304f7e); font-size: 11.5px; font-weight: 750; cursor: pointer; }
.text-button--quiet { color: var(--muted, #6b7a8f); }
.text-button:hover:not(:disabled) { text-decoration: underline; }
@media (max-width: 640px) {
  .catalog-form { grid-template-columns: 1fr; }
  .catalog-list li { grid-template-columns: auto minmax(0, 1fr); }
  .catalog-list li .status, .catalog-list li .catalog-actions { grid-column: 2; }
}
</style>
