<script setup lang="ts">
import { Pencil, Plus, Search, Upload } from "lucide-vue-next";
import type { CatalogList, Supplier } from "~/types/equipment";
import Button from "~/components/ui/Button.vue";
import SupplierImportModal from "~/components/supplier/SupplierImportModal.vue";
import SupplierForm, { type SupplierFormValues } from "~/components/supplier/SupplierForm.vue";
import { useIncrementalList } from "~/composables/useIncrementalList";
import { formatCnpj, sortSuppliers } from "~/utils/suppliers";

definePageMeta({ middleware: "auth" });
const api = useApi();
const auth = useAuthStore();

const suppliers = ref<Supplier[]>([]);
const loading = ref(true);
const saving = ref(false);
let loadVersion = 0;
const error = ref("");
const formError = ref("");
const search = ref("");
const includeInactive = ref(false);
const showForm = ref(false);
const showImport = ref(false);
const editing = ref<Supplier | null>(null);

const { root: listRoot, sentinel, visible: visibleSuppliers, total, hasMore } = useIncrementalList(() => suppliers.value);
const numberFormat = new Intl.NumberFormat("pt-BR");

const allowed = computed(() => auth.can("suppliers:read"));
const canWrite = computed(() => auth.can("suppliers:write"));

async function load(): Promise<void> {
  const version = ++loadVersion;
  loading.value = true;
  error.value = "";
  try {
    const query: Record<string, unknown> = {};
    if (search.value.trim()) query.search = search.value.trim();
    if (includeInactive.value) query.includeInactive = true;
    const result = sortSuppliers((await api.get<CatalogList<Supplier>>("/suppliers", query)).items);
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

function openCreate(): void {
  editing.value = null;
  formError.value = "";
  showForm.value = true;
}

function openEdit(supplier: Supplier): void {
  editing.value = supplier;
  formError.value = "";
  showForm.value = true;
}

async function submit(values: SupplierFormValues): Promise<void> {
  if (saving.value) return;
  saving.value = true;
  formError.value = "";
  try {
    if (editing.value) {
      await api.patch(`/suppliers/${editing.value.id}`, values);
    } else {
      await api.post("/suppliers", values);
    }
    showForm.value = false;
    await load();
  } catch (caught) {
    formError.value =
      caught instanceof Error ? caught.message : "Não foi possível salvar o fornecedor.";
  } finally {
    saving.value = false;
  }
}

onMounted(() => {
  if (!allowed.value) {
    loading.value = false;
    return;
  }
  return load();
});
</script>

<template>
  <ModuleWorkspace
    eyebrow="Planejamento · Equipamentos"
    title="Fornecedores"
    description="Cadastro mestre usado nos vínculos com equipamentos."
  >
    <div v-if="!allowed" class="surface empty-state state-card" role="alert">
      <h2>Sem permissão</h2><p>Seu perfil não tem acesso ao cadastro de fornecedores.</p>
    </div>
    <div v-else class="stack">
      <section class="surface filter-surface" aria-label="Filtros de fornecedores">
        <div class="filter-grid">
          <form class="field" @submit.prevent="load">
            <span>Busca</span>
            <div class="search-control">
              <input v-model="search" placeholder="Código, razão social, nome fantasia ou CNPJ">
              <Button variant="outline" type="submit" :loading="loading">
                <Search v-if="!loading" :size="16" /> {{ loading ? "Buscando..." : "Buscar" }}
              </Button>
            </div>
          </form>
          <label class="field field-check">
            <input v-model="includeInactive" type="checkbox" @change="load">
            <span>Mostrar inativos</span>
          </label>
          <div class="filter-actions">
            <Button v-if="canWrite" variant="default" @click="openCreate">
              <Plus :size="16" /> Novo fornecedor
            </Button>
            <Button v-if="canWrite" variant="outline" @click="showImport = true">
              <Upload :size="16" /> Importar planilha
            </Button>
          </div>
        </div>
      </section>

      <section class="surface list-card">
        <div class="surface-header">
          <div>
            <h2>Cadastro de fornecedores</h2>
            <p>
              {{ numberFormat.format(total) }} fornecedor(es) em ordem alfabética<template v-if="total">
                · Exibindo {{ numberFormat.format(visibleSuppliers.length) }} de {{ numberFormat.format(total) }}</template>.
            </p>
          </div>
        </div>
        <div v-if="loading && !suppliers.length" class="list-state" role="status"><span class="spinner" /> Carregando fornecedores...</div>
        <div v-else-if="error" class="empty-state table-empty" role="alert">
          <h2>Não foi possível carregar</h2><p>{{ error }}</p>
          <Button variant="outline" @click="load">Tentar novamente</Button>
        </div>
        <div v-else-if="suppliers.length === 0" class="empty-state table-empty">
          <h2>Nenhum fornecedor cadastrado</h2>
          <p>Cadastre o primeiro fornecedor para vinculá-lo a equipamentos.</p>
        </div>
        <div v-else ref="listRoot" class="table-wrap" :class="{ refreshing: loading }" :aria-busy="loading" data-testid="supplier-scroll">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Código</TableHead>
                <TableHead>Razão social</TableHead>
                <TableHead>Nome fantasia</TableHead>
                <TableHead>CNPJ</TableHead>
                <TableHead>Situação</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow v-for="supplier in visibleSuppliers" :key="supplier.id">
                <TableCell><span class="supplier-code">{{ supplier.corporateCode ?? "—" }}</span></TableCell>
                <TableCell class="font-semibold supplier-name">{{ supplier.legalName }}</TableCell>
                <TableCell>{{ supplier.tradeName ?? "—" }}</TableCell>
                <TableCell class="cnpj">{{ formatCnpj(supplier.taxId) }}</TableCell>
                <TableCell>
                  <span class="status" :class="supplier.active ? 'status--on' : 'status--off'">
                    {{ supplier.active ? "Ativo" : "Inativo" }}
                  </span>
                </TableCell>
                <TableCell>
                  <Button v-if="canWrite" class="text-button" variant="ghost" size="sm" @click="openEdit(supplier)">
                    <Pencil :size="13" /> Editar
                  </Button>
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
          <div v-if="hasMore" ref="sentinel" class="list-sentinel" data-testid="supplier-sentinel">
            <span class="spinner spinner-small" /> Carregando mais fornecedores...
          </div>
        </div>
      </section>
    </div>

    <SupplierImportModal :open="showImport" @close="showImport = false" @imported="load" />

    <AppModal :open="showForm" :title="editing ? 'Editar fornecedor' : 'Novo fornecedor'" @close="showForm = false">
      <SupplierForm
        :supplier="editing"
        :saving="saving"
        :error="formError"
        @submit="submit"
        @cancel="showForm = false"
      />
    </AppModal>
  </ModuleWorkspace>
</template>

<style scoped>
.state-card { max-width: none; }
.filter-surface { padding: 16px 18px; }
.filter-grid { display: grid; grid-template-columns: minmax(280px, 1.4fr) auto auto; align-items: end; gap: 14px; }
.search-control { display: flex; gap: 7px; }
.field-check { display: flex; align-items: center; gap: 8px; padding-bottom: 8px; }
.field-check input { width: 15px; height: 15px; }
.field-check span { color: #2b3e58; font-size: 12px; font-weight: 700; }
.filter-actions { display: flex; gap: 8px; }
.list-state { display: flex; min-height: 200px; align-items: center; justify-content: center; gap: 12px; color: #748197; }
.list-card { display: flex; min-width: 0; height: calc(100vh - 330px); min-height: 360px; max-height: 760px; flex-direction: column; overflow: hidden; }
.list-card > .surface-header { flex: 0 0 auto; }
.table-wrap { min-height: 0; flex: 1 1 auto; padding: 0 18px 18px; overflow: auto; overscroll-behavior: contain; }
.table-wrap :deep(thead th) { position: sticky; top: 0; z-index: 1; background: #fff; }
.table-wrap { transition: opacity 0.15s ease; }
.table-wrap.refreshing { opacity: 0.6; }
.list-sentinel { display: flex; align-items: center; justify-content: center; gap: 8px; padding: 14px; color: #748197; font-size: 12px; }
.supplier-code { display: inline-flex; border-radius: 6px; padding: 3px 7px; background: #eef4fb; color: #315889; font-size: 11px; font-weight: 800; white-space: nowrap; }
.supplier-name { min-width: 220px; color: #263d5d; }
.cnpj { font-variant-numeric: tabular-nums; white-space: nowrap; }
.table-empty { margin: auto; padding-bottom: 28px; }
.status { border-radius: 999px; padding: 4px 9px; font-size: 11px; font-weight: 750; }
.status--on { background: #eaf4e5; color: #477a32; }
.status--off { background: #eef2f7; color: #6b7a8f; }
@media (max-width: 860px) { .filter-grid { grid-template-columns: 1fr; } .list-card { height: calc(100vh - 200px); } }
</style>
