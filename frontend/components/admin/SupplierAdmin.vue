<script setup lang="ts">
import { reactive, ref } from "vue";
import { Pencil, Plus, Search } from "lucide-vue-next";
import type { CatalogList, Supplier } from "~/types/equipment";

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
const error = ref("");
const formError = ref("");
const editing = ref<Supplier | null>(null);
const creating = ref(false);
const form = reactive({ legalName: "", tradeName: "", taxId: "", active: true });

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

function startCreate(): void {
  creating.value = true;
  editing.value = null;
  formError.value = "";
  Object.assign(form, { legalName: "", tradeName: "", taxId: "", active: true });
}

function startEdit(supplier: Supplier): void {
  creating.value = false;
  editing.value = supplier;
  formError.value = "";
  Object.assign(form, {
    legalName: supplier.legalName,
    tradeName: supplier.tradeName ?? "",
    taxId: supplier.taxId ?? "",
    active: supplier.active,
  });
}

function cancel(): void {
  creating.value = false;
  editing.value = null;
  formError.value = "";
}

async function submit(): Promise<void> {
  if (!form.legalName.trim()) {
    formError.value = "Informe a razão social.";
    return;
  }
  saving.value = true;
  formError.value = "";
  const payload: Record<string, unknown> = {
    legalName: form.legalName.trim(),
    tradeName: form.tradeName.trim() || null,
    taxId: form.taxId.trim() || null,
  };
  try {
    if (editing.value) await api.patch(`/suppliers/${editing.value.id}`, { ...payload, active: form.active });
    else await api.post("/suppliers", payload);
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
  if (supplier.active && !confirm(`Desativar "${supplier.legalName}"? Ele não poderá ser vinculado.`)) {
    return;
  }
  saving.value = true;
  error.value = "";
  try {
    await api.patch(`/suppliers/${supplier.id}`, { active: !supplier.active });
    await load();
    emit("changed");
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "Não foi possível alterar a situação.";
  } finally {
    saving.value = false;
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
    @close="emit('close')"
  >
    <div class="supplier-admin" data-testid="supplier-admin">
      <div class="supplier-toolbar">
        <form class="field supplier-search" @submit.prevent="load">
          <span>Busca</span>
          <div class="search-control">
            <input v-model="search" placeholder="Razão social ou nome fantasia">
            <button type="submit" class="btn small"><Search :size="13" /> Buscar</button>
          </div>
        </form>
        <label class="field-check">
          <input v-model="includeInactive" type="checkbox" @change="load"><span>Mostrar inativos</span>
        </label>
        <button type="button" class="btn small primary" @click="startCreate">
          <Plus :size="13" /> Novo
        </button>
      </div>

      <form v-if="creating || editing" class="supplier-form" @submit.prevent="submit">
        <label class="field"><span>Razão social *</span><input v-model="form.legalName" maxlength="200" required></label>
        <label class="field"><span>Nome fantasia</span><input v-model="form.tradeName" maxlength="200"></label>
        <label class="field"><span>Documento</span><input v-model="form.taxId" maxlength="32" placeholder="Opcional"></label>
        <label v-if="editing" class="field-check">
          <input v-model="form.active" type="checkbox"><span>Ativo</span>
        </label>
        <div class="supplier-form-actions">
          <button type="button" class="btn small" @click="cancel">Cancelar</button>
          <button type="submit" class="btn small primary" :disabled="saving">
            {{ saving ? "Salvando..." : "Salvar" }}
          </button>
        </div>
        <p v-if="formError" class="supplier-error" role="alert">{{ formError }}</p>
      </form>

      <p v-if="loading" class="supplier-hint"><span class="spinner spinner-small" /> Carregando...</p>
      <p v-else-if="error" class="supplier-error" role="alert">{{ error }}</p>
      <p v-else-if="suppliers.length === 0" class="supplier-hint" data-testid="supplier-admin-empty">
        Nenhum fornecedor encontrado.
      </p>
      <ul v-else class="supplier-list">
        <li v-for="supplier in suppliers" :key="supplier.id" :data-testid="`supplier-row-${supplier.id}`">
          <span class="supplier-name">
            <strong>{{ supplier.legalName }}</strong>
            <small>{{ supplier.tradeName ?? "—" }} · {{ supplier.taxId ?? "sem documento" }}</small>
          </span>
          <span class="supplier-actions">
            <span class="status" :class="supplier.active ? 'status--on' : 'status--off'">
              {{ supplier.active ? "Ativo" : "Inativo" }}
            </span>
            <button type="button" class="text-button" :disabled="saving" @click="startEdit(supplier)">
              <Pencil :size="12" /> Editar
            </button>
            <button type="button" class="text-button" :disabled="saving" @click="toggleActive(supplier)">
              {{ supplier.active ? "Desativar" : "Reativar" }}
            </button>
          </span>
        </li>
      </ul>

      <p class="supplier-footer">
        <NuxtLink to="/fornecedores">Ver todos os fornecedores</NuxtLink>
      </p>
    </div>
  </AdminPanel>
</template>

<style scoped>
.supplier-admin { display: grid; gap: 12px; }
.supplier-toolbar { display: flex; flex-wrap: wrap; align-items: end; gap: 12px; }
.supplier-search { flex: 1 1 280px; }
.search-control { display: flex; gap: 6px; }
.field-check { display: flex; align-items: center; gap: 7px; padding-bottom: 7px; color: #2b3e58; font-size: 12px; font-weight: 700; }
.field-check input { width: 15px; height: 15px; }
.supplier-form { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; border: 1px solid #e4e9f0; border-radius: 10px; padding: 12px; background: #f8fafc; }
.supplier-form-actions { display: flex; grid-column: 1 / -1; justify-content: flex-end; gap: 8px; }
.supplier-form .supplier-error { grid-column: 1 / -1; }
.supplier-hint { display: flex; align-items: center; gap: 8px; margin: 0; color: #8b96a5; font-size: 12px; }
.supplier-error { margin: 0; color: #a4453a; font-size: 12px; font-weight: 700; }
.supplier-list { display: grid; margin: 0; padding: 0; gap: 2px; list-style: none; }
.supplier-list li { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 8px 12px; border-bottom: 1px solid #f0f3f7; padding: 8px 2px; }
.supplier-list li:last-child { border-bottom: 0; }
.supplier-name { display: grid; min-width: 0; flex: 1 1 200px; gap: 2px; }
.supplier-name strong { color: #2b3e58; font-size: 12.5px; }
.supplier-name small { color: #8b96a5; font-size: 11px; }
.supplier-actions { display: flex; flex: 0 0 auto; align-items: center; gap: 10px; }
.status { border-radius: 999px; padding: 3px 8px; font-size: 10.5px; font-weight: 750; }
.status--on { background: #eaf4e5; color: #477a32; }
.status--off { background: #eef2f7; color: #6b7a8f; }
.text-button { display: inline-flex; align-items: center; gap: 4px; border: 0; padding: 2px; background: transparent; color: #304f7e; font-size: 11.5px; font-weight: 750; }
.supplier-footer { margin: 0; text-align: right; }
.supplier-footer a { color: #304f7e; font-size: 12px; font-weight: 750; text-decoration: none; }
.spinner-small { width: 14px; height: 14px; border-width: 2px; }
@media (max-width: 620px) { .supplier-form { grid-template-columns: 1fr; } }
</style>
