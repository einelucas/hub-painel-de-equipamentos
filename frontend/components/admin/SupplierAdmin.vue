<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { Pencil, Plus, Search, Upload } from "lucide-vue-next";
import SupplierImportModal from "~/components/supplier/SupplierImportModal.vue";
import SupplierForm, { type SupplierFormValues } from "~/components/supplier/SupplierForm.vue";
import type { CatalogList, Supplier } from "~/types/equipment";
import { useIncrementalList } from "~/composables/useIncrementalList";
import { formatCnpj } from "~/utils/suppliers";

/**
 * Cadastro mestre de fornecedores, contextual à aba Suprimentos.
 * O vínculo fornecedor ↔ equipamento continua no detalhe do equipamento.
 */
const props = defineProps<{ open: boolean }>();
const emit = defineEmits<{ close: []; changed: [] }>();

const api = useApi();
const section = ref("suppliers");
const suppliers = ref<Supplier[]>([]);
const search = ref("");
const includeInactive = ref(false);
const loading = ref(false);
const saving = ref(false);
const togglingId = ref<string | null>(null);
let loadVersion = 0;
const error = ref("");
const formError = ref("");
const editing = ref<Supplier | null>(null);
const creating = ref(false);
const showImport = ref(false);

async function onImported(): Promise<void> {
  await load();
  emit("changed");
}

const { root: listRoot, sentinel, visible: visibleSuppliers, total, hasMore } = useIncrementalList(() => suppliers.value);
const numberFormat = new Intl.NumberFormat("pt-BR");

const activeCount = computed(() => suppliers.value.filter((item) => item.active).length);
const inactiveCount = computed(() => suppliers.value.length - activeCount.value);

async function load(): Promise<void> {
  const version = ++loadVersion;
  loading.value = true;
  error.value = "";
  try {
    const query: Record<string, unknown> = {};
    if (search.value.trim()) query.search = search.value.trim();
    if (includeInactive.value) query.includeInactive = true;
    const result = (await api.get<CatalogList<Supplier>>("/suppliers", query)).items;
    if (version !== loadVersion) return;
    suppliers.value = result;
  } catch (caught) {
    if (version !== loadVersion) return;
    error.value =
      caught instanceof Error ? caught.message : "Não foi possível carregar os fornecedores.";
  } finally {
    if (version === loadVersion) loading.value = false;
  }
}

// Busca ao digitar, com uma pausa curta para não consultar a cada tecla.
let searchTimer: ReturnType<typeof setTimeout> | undefined;
watch(search, () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => void load(), 300);
});
onBeforeUnmount(() => clearTimeout(searchTimer));

function startCreate(): void {
  creating.value = true;
  editing.value = null;
  formError.value = "";
}

function startEdit(supplier: Supplier): void {
  creating.value = false;
  editing.value = supplier;
  formError.value = "";
}

function cancel(): void {
  creating.value = false;
  editing.value = null;
  formError.value = "";
}

async function submit(values: SupplierFormValues): Promise<void> {
  if (saving.value) return;
  saving.value = true;
  formError.value = "";
  try {
    if (editing.value) await api.patch(`/suppliers/${editing.value.id}`, values);
    else await api.post("/suppliers", values);
    cancel();
    await load();
    emit("changed");
  } catch (caught) {
    formError.value =
      caught instanceof Error ? caught.message : "Não foi possível salvar o fornecedor.";
  } finally {
    saving.value = false;
  }
}

/** Sem exclusão física: o fornecedor pode estar vinculado a equipamentos. */
async function toggleActive(supplier: Supplier): Promise<void> {
  if (saving.value) return;
  if (supplier.active && !confirm(`Desativar "${supplier.legalName}"? Ele não poderá ser vinculado.`)) {
    return;
  }
  saving.value = true;
  togglingId.value = supplier.id;
  error.value = "";
  try {
    await api.patch(`/suppliers/${supplier.id}`, { active: !supplier.active });
    await load();
    emit("changed");
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "Não foi possível alterar a situação.";
  } finally {
    saving.value = false;
    togglingId.value = null;
  }
}

watch(() => props.open, (open) => { if (open) void load(); }, { immediate: true });
</script>

<template>
  <AdminPanel
    v-model:section="section"
    :open="props.open"
    title="Administração · Fornecedores"
    description="Cadastro mestre. O vínculo com cada equipamento continua no detalhe do equipamento."
    :sections="[{ key: 'suppliers', label: 'Fornecedores' }]"
    contained
    @close="emit('close')"
  >
    <section class="supplier-admin admin-fill" data-testid="supplier-admin">
      <header class="supplier-header">
        <div>
          <h3>Fornecedores</h3>
          <p class="supplier-count">
            <template v-if="loading && !suppliers.length">Carregando…</template>
            <template v-else>
              {{ activeCount }} ativo{{ activeCount === 1 ? "" : "s" }}<template v-if="inactiveCount"> · {{ inactiveCount }} inativo{{ inactiveCount === 1 ? "" : "s" }}</template><template v-if="search.trim()"> na busca</template>
            </template>
            <span v-if="loading && suppliers.length" class="spinner-small" role="status" aria-label="Atualizando" />
          </p>
        </div>
        <div class="supplier-header-actions">
          <button type="button" class="btn small" :disabled="saving" data-testid="supplier-import-open" @click="showImport = true">
            <Upload :size="14" /> Importar planilha
          </button>
          <button type="button" class="btn small primary" :disabled="saving" @click="startCreate">
            <Plus :size="14" /> Novo
          </button>
        </div>
      </header>

      <SupplierImportModal :open="showImport" @close="showImport = false" @imported="onImported" />

      <div class="supplier-toolbar">
        <label class="supplier-search">
          <Search :size="14" aria-hidden="true" />
          <input
            v-model="search"
            type="search"
            placeholder="Buscar por razão social ou nome fantasia"
            aria-label="Buscar fornecedores"
          >
        </label>
        <label class="inactive-toggle" :class="{ on: includeInactive }">
          <input v-model="includeInactive" type="checkbox" @change="load">
          <span>Mostrar inativos</span>
        </label>
      </div>

      <SupplierForm
        v-if="creating || editing"
        :supplier="editing"
        :saving="saving"
        :error="formError"
        compact
        @submit="submit"
        @cancel="cancel"
      />

      <p v-if="loading && !suppliers.length" class="supplier-hint"><span class="spinner spinner-small" /> Carregando...</p>
      <p v-else-if="error" class="supplier-error" role="alert">{{ error }}</p>
      <p v-else-if="suppliers.length === 0" class="supplier-empty" data-testid="supplier-admin-empty">
        {{ search.trim() ? "Nenhum fornecedor corresponde à busca." : "Nenhum fornecedor cadastrado. Use \"Novo\" para criar o primeiro." }}
      </p>
      <ul v-else ref="listRoot" class="supplier-list" :class="{ refreshing: loading }" data-testid="supplier-scroll">
        <li
          v-for="supplier in visibleSuppliers"
          :key="supplier.id"
          :class="{ inactive: !supplier.active, editing: supplier.id === editing?.id }"
          :data-testid="`supplier-row-${supplier.id}`"
        >
          <span class="supplier-code" :title="supplier.corporateCode ? 'Código corporativo' : 'Cadastrado manualmente'">
            {{ supplier.corporateCode ?? "—" }}
          </span>
          <span class="supplier-name">
            <strong>{{ supplier.legalName }}</strong>
            <small>
              <template v-if="supplier.tradeName">{{ supplier.tradeName }} · </template>
              <span v-if="supplier.taxId" class="cnpj">{{ formatCnpj(supplier.taxId) }}</span>
              <span v-else class="missing">sem CNPJ</span>
            </small>
          </span>
          <span class="status" :class="supplier.active ? 'status--on' : 'status--off'">
            {{ supplier.active ? "Ativo" : "Inativo" }}
          </span>
          <span class="supplier-actions">
            <button type="button" class="text-button" :disabled="saving" @click="startEdit(supplier)">
              <Pencil :size="12" /> Editar
            </button>
            <button
              type="button"
              class="text-button"
              :class="{ 'text-button--quiet': supplier.active }"
              :disabled="saving"
              :aria-busy="togglingId === supplier.id"
              @click="toggleActive(supplier)"
            >
              <span v-if="togglingId === supplier.id" class="spinner-small" aria-hidden="true" />
              {{ togglingId === supplier.id ? "Salvando..." : supplier.active ? "Desativar" : "Reativar" }}
            </button>
          </span>
        </li>
        <li v-if="hasMore" ref="sentinel" class="supplier-sentinel" data-testid="supplier-sentinel">
          <span class="spinner spinner-small" /> Carregando mais...
        </li>
      </ul>
      <p v-if="total && !error" class="supplier-shown" data-testid="supplier-shown">
        Exibindo {{ numberFormat.format(visibleSuppliers.length) }} de {{ numberFormat.format(total) }}
      </p>

      <p class="supplier-footer">
        <NuxtLink to="/fornecedores">Ver todos os fornecedores</NuxtLink>
      </p>
    </section>
  </AdminPanel>
</template>

<style scoped>
/* Cabeçalho, busca e formulário ficam parados; só a lista rola (dentro do painel). */
.supplier-admin { display: flex; flex-direction: column; gap: 12px; }
.supplier-admin > * { flex: 0 0 auto; }
.supplier-header { display: flex; align-items: flex-end; justify-content: space-between; gap: 12px; padding-bottom: 10px; border-bottom: 1px solid var(--rule, #dde5ef); }
.supplier-header h3 { margin: 0; color: var(--ink, #1f3352); font-size: 17px; font-weight: 800; letter-spacing: -0.01em; }
.supplier-header-actions { display: flex; gap: 8px; }
.supplier-count { margin: 2px 0 0; color: var(--muted, #6b7a8f); font-family: var(--mono, monospace); font-size: 11px; }

.supplier-toolbar { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; }
.supplier-search { display: flex; min-width: 240px; flex: 1 1 320px; align-items: center; gap: 8px; border: 1px solid var(--rule, #dde5ef); border-radius: 9px; padding: 0 10px; background: #fff; color: var(--muted, #6b7a8f); }
.supplier-search:focus-within { border-color: var(--steel, #304f7e); box-shadow: 0 0 0 2px rgb(48 79 126 / 12%); }
.supplier-search input { min-width: 0; flex: 1; border: 0; outline: 0; padding: 8px 0; background: transparent; color: var(--ink, #1f3352); font-size: 12.5px; }
.inactive-toggle { display: inline-flex; align-items: center; gap: 7px; border: 1px solid var(--rule, #dde5ef); border-radius: 9px; padding: 8px 11px; background: #fff; color: var(--muted, #6b7a8f); font-size: 12px; font-weight: 700; cursor: pointer; }
.inactive-toggle.on { border-color: var(--steel, #304f7e); background: #f1f6fd; color: var(--ink, #1f3352); }
.inactive-toggle:focus-within { outline: 2px solid var(--steel, #304f7e); outline-offset: 2px; }
.inactive-toggle input { width: 14px; height: 14px; accent-color: var(--steel, #304f7e); }


.supplier-hint { display: flex; align-items: center; gap: 8px; margin: 0; color: var(--muted, #6b7a8f); font-size: 12px; }
.supplier-error { margin: 0; color: var(--stop, #a4453a); font-size: 12px; font-weight: 700; }
.supplier-empty { margin: 0; border: 1px dashed var(--rule, #dde5ef); border-radius: 12px; padding: 22px; color: var(--muted, #6b7a8f); font-size: 12.5px; text-align: center; }

/* Encolhe até caber no painel e rola; lista curta continua curta. */
.supplier-admin > .supplier-list { min-height: 0; flex: 0 1 auto; }
.supplier-list { display: block; margin: 0; padding: 0; border: 1px solid var(--rule, #dde5ef); border-radius: 12px; list-style: none; overflow-y: auto; overscroll-behavior: contain; transition: opacity 0.15s ease; }
.supplier-list.refreshing { opacity: 0.6; }
.supplier-list li {
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr) auto auto;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  border-bottom: 1px solid #edf1f6;
  background: #fff;
}
.supplier-list li:last-child { border-bottom: 0; }
.supplier-list li:hover { background: #fafcfe; }
.supplier-list li.editing { background: #f1f6fd; }
.supplier-list li.inactive .supplier-name strong, .supplier-list li.inactive .supplier-code { color: #9aa6b5; }
.supplier-code { overflow: hidden; color: var(--steel, #304f7e); font-family: var(--mono, monospace); font-size: 12px; font-weight: 700; text-overflow: ellipsis; white-space: nowrap; }
.supplier-name { display: grid; min-width: 0; gap: 2px; }
.supplier-name strong { overflow: hidden; color: var(--ink, #1f3352); font-size: 12.5px; font-weight: 700; text-overflow: ellipsis; white-space: nowrap; }
.supplier-name small { overflow: hidden; color: var(--muted, #6b7a8f); font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
.cnpj { font-family: var(--mono, monospace); font-variant-numeric: tabular-nums; letter-spacing: 0.01em; }
.missing { color: #a3adbb; font-style: italic; }
.status { display: inline-flex; align-items: center; gap: 5px; font-size: 11px; font-weight: 750; }
.status::before { width: 7px; height: 7px; border-radius: 999px; background: currentColor; content: ""; }
.status--on { color: var(--go, #3f7a2e); }
.status--off { color: #9aa6b5; }
.supplier-actions { display: flex; align-items: center; gap: 12px; }
.text-button { display: inline-flex; align-items: center; gap: 4px; border: 0; padding: 2px; background: transparent; color: var(--steel, #304f7e); font-size: 11.5px; font-weight: 750; cursor: pointer; }
.text-button--quiet { color: var(--muted, #6b7a8f); }
.text-button:hover:not(:disabled) { text-decoration: underline; }

.supplier-shown { margin: -4px 0 0; color: var(--muted, #6b7a8f); font-family: var(--mono, monospace); font-size: 11px; }
.supplier-list li.supplier-sentinel { display: flex; justify-content: center; gap: 8px; color: var(--muted, #6b7a8f); font-size: 12px; }
.supplier-footer { margin: 0; text-align: right; }
.supplier-footer a { color: var(--steel, #304f7e); font-size: 12px; font-weight: 750; text-decoration: none; }
.supplier-footer a:hover { text-decoration: underline; }
@media (max-width: 640px) {
  .supplier-list li { grid-template-columns: minmax(0, 1fr) auto; }
  .supplier-code { display: none; }
  .supplier-list li .supplier-actions { grid-column: 1 / -1; }
}
@media (prefers-reduced-motion: reduce) { .supplier-list { transition: none; } }
</style>
