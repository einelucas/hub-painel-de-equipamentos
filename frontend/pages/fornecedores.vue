<script setup lang="ts">
import { Pencil, Plus, Search } from "lucide-vue-next";
import type { CatalogList, Supplier } from "~/types/equipment";

definePageMeta({ middleware: "auth" });
const api = useApi();
const auth = useAuthStore();

const suppliers = ref<Supplier[]>([]);
const loading = ref(true);
const saving = ref(false);
const error = ref("");
const formError = ref("");
const search = ref("");
const includeInactive = ref(false);
const showForm = ref(false);
const editing = ref<Supplier | null>(null);
const form = reactive({ legalName: "", tradeName: "", taxId: "", active: true });

const allowed = computed(() => auth.can("suppliers:read"));
const canWrite = computed(() => auth.can("suppliers:write"));

async function load(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    const query: Record<string, unknown> = {};
    if (search.value.trim()) query.search = search.value.trim();
    if (includeInactive.value) query.includeInactive = true;
    suppliers.value = (await api.get<CatalogList<Supplier>>("/suppliers", query)).items;
  } catch (caught) {
    error.value =
      caught instanceof Error ? caught.message : "Não foi possível carregar os fornecedores.";
  } finally {
    loading.value = false;
  }
}

function openCreate(): void {
  editing.value = null;
  formError.value = "";
  Object.assign(form, { legalName: "", tradeName: "", taxId: "", active: true });
  showForm.value = true;
}

function openEdit(supplier: Supplier): void {
  editing.value = supplier;
  formError.value = "";
  Object.assign(form, {
    legalName: supplier.legalName,
    tradeName: supplier.tradeName ?? "",
    taxId: supplier.taxId ?? "",
    active: supplier.active,
  });
  showForm.value = true;
}

async function submit(): Promise<void> {
  if (!form.legalName.trim()) {
    formError.value = "Informe a razão social.";
    return;
  }
  saving.value = true;
  formError.value = "";
  const payload = {
    legalName: form.legalName.trim(),
    tradeName: form.tradeName.trim() || null,
    taxId: form.taxId.trim() || null,
  };
  try {
    if (editing.value) {
      await api.patch(`/suppliers/${editing.value.id}`, { ...payload, active: form.active });
    } else {
      await api.post("/suppliers", payload);
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
              <input v-model="search" placeholder="Razão social ou nome fantasia">
              <button class="btn" type="submit"><Search :size="16" /> Buscar</button>
            </div>
          </form>
          <label class="field field-check">
            <input v-model="includeInactive" type="checkbox" @change="load">
            <span>Mostrar inativos</span>
          </label>
          <div class="filter-actions">
            <button v-if="canWrite" class="btn primary" @click="openCreate">
              <Plus :size="16" /> Novo fornecedor
            </button>
          </div>
        </div>
      </section>

      <section class="surface">
        <div class="surface-header">
          <div><h2>Cadastro</h2><p>{{ suppliers.length }} fornecedor(es) listado(s).</p></div>
        </div>
        <div v-if="loading" class="list-state"><span class="spinner" /> Carregando fornecedores...</div>
        <div v-else-if="error" class="empty-state table-empty" role="alert">
          <h2>Não foi possível carregar</h2><p>{{ error }}</p>
          <button class="btn" @click="load">Tentar novamente</button>
        </div>
        <div v-else-if="suppliers.length === 0" class="empty-state table-empty">
          <h2>Nenhum fornecedor cadastrado</h2>
          <p>Cadastre o primeiro fornecedor para vinculá-lo a equipamentos.</p>
        </div>
        <div v-else class="table-wrap">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Razão social</TableHead>
                <TableHead>Nome fantasia</TableHead>
                <TableHead>Documento</TableHead>
                <TableHead>Situação</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow v-for="supplier in suppliers" :key="supplier.id">
                <TableCell class="font-semibold">{{ supplier.legalName }}</TableCell>
                <TableCell>{{ supplier.tradeName ?? "—" }}</TableCell>
                <TableCell>{{ supplier.taxId ?? "—" }}</TableCell>
                <TableCell>
                  <span class="status" :class="supplier.active ? 'status--on' : 'status--off'">
                    {{ supplier.active ? "Ativo" : "Inativo" }}
                  </span>
                </TableCell>
                <TableCell>
                  <button v-if="canWrite" class="text-button" @click="openEdit(supplier)">
                    <Pencil :size="13" /> Editar
                  </button>
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </div>
      </section>
    </div>

    <AppModal :open="showForm" :title="editing ? 'Editar fornecedor' : 'Novo fornecedor'" @close="showForm = false">
      <form class="supplier-form" @submit.prevent="submit">
        <label class="field"><span>Razão social *</span><input v-model="form.legalName" maxlength="200" required></label>
        <label class="field"><span>Nome fantasia</span><input v-model="form.tradeName" maxlength="200"></label>
        <label class="field"><span>Documento</span><input v-model="form.taxId" maxlength="32" placeholder="Opcional"></label>
        <label v-if="editing" class="field field-check">
          <input v-model="form.active" type="checkbox"><span>Fornecedor ativo</span>
        </label>
        <p v-if="editing" class="form-hint">Fornecedores não são excluídos: desative para tirá-los de uso.</p>
        <p v-if="formError" class="notice error" role="alert">{{ formError }}</p>
        <div class="form-actions">
          <button type="button" class="btn" @click="showForm = false">Cancelar</button>
          <button type="submit" class="btn primary" :disabled="saving">{{ saving ? "Salvando..." : "Salvar" }}</button>
        </div>
      </form>
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
.table-wrap { padding: 0 18px 18px; overflow-x: auto; }
.table-empty { margin: auto; padding-bottom: 28px; }
.status { border-radius: 999px; padding: 4px 9px; font-size: 11px; font-weight: 750; }
.status--on { background: #eaf4e5; color: #477a32; }
.status--off { background: #eef2f7; color: #6b7a8f; }
.text-button { display: inline-flex; align-items: center; gap: 5px; border: 0; padding: 4px; background: transparent; color: #304f7e; font-size: 12px; font-weight: 750; }
.supplier-form { display: grid; gap: 14px; }
.form-hint { margin: -6px 0 0; color: #8b96a5; font-size: 11.5px; }
.form-actions { display: flex; justify-content: flex-end; gap: 9px; }
@media (max-width: 860px) { .filter-grid { grid-template-columns: 1fr; } }
</style>
