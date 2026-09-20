<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";
import { Check, Pencil, Plus, X } from "lucide-vue-next";
import type { CatalogItem, CatalogList } from "~/types/equipment";

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
  /** Mensagem quando falta selecionar o pai (unidade/contexto). */
  requiresParent?: string;
}>();
const emit = defineEmits<{ changed: [] }>();

const api = useApi();
const items = ref<CatalogItem[]>([]);
const loading = ref(false);
const saving = ref(false);
const error = ref("");
const formError = ref("");
const editingId = ref<string | null>(null);
const creating = ref(false);
const form = reactive({ name: "", code: "" });

const blocked = computed(() => Boolean(props.requiresParent));

async function load(): Promise<void> {
  if (blocked.value) {
    items.value = [];
    return;
  }
  loading.value = true;
  error.value = "";
  try {
    items.value = (await api.get<CatalogList<CatalogItem>>(props.path, props.query)).items;
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : `Não foi possível carregar ${props.label}.`;
  } finally {
    loading.value = false;
  }
}

function startCreate(): void {
  creating.value = true;
  editingId.value = null;
  formError.value = "";
  form.name = "";
  form.code = "";
}

function startEdit(item: CatalogItem): void {
  creating.value = false;
  editingId.value = item.id;
  formError.value = "";
  form.name = item.name;
  form.code = item.code ?? "";
}

function cancel(): void {
  creating.value = false;
  editingId.value = null;
  formError.value = "";
}

async function submit(): Promise<void> {
  if (!form.name.trim() || (props.hasCode && !form.code.trim())) {
    formError.value = props.hasCode ? "Informe código e nome." : "Informe o nome.";
    return;
  }
  saving.value = true;
  formError.value = "";
  const payload: Record<string, unknown> = { name: form.name.trim() };
  if (props.hasCode) payload.code = form.code.trim();
  try {
    if (editingId.value) await api.patch(`${props.path}/${editingId.value}`, payload);
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
  if (item.active && !confirm(`Desativar "${item.name}"? Ele deixa de aparecer nos formulários.`)) {
    return;
  }
  saving.value = true;
  error.value = "";
  try {
    await api.patch(`${props.path}/${item.id}`, { active: !item.active });
    await load();
    emit("changed");
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "Não foi possível alterar a situação.";
  } finally {
    saving.value = false;
  }
}

watch(() => [props.path, props.query, props.requiresParent], load, { deep: true, immediate: true });
</script>

<template>
  <section class="catalog" :data-testid="`catalog-${props.label.toLowerCase()}`">
    <header class="catalog-header">
      <h3>{{ props.label }}</h3>
      <button v-if="!blocked" type="button" class="btn small" :disabled="saving" @click="startCreate">
        <Plus :size="14" /> Novo
      </button>
    </header>

    <p v-if="blocked" class="catalog-hint" data-testid="catalog-blocked">{{ props.requiresParent }}</p>
    <template v-else>
      <form v-if="creating || editingId" class="catalog-form" @submit.prevent="submit">
        <label v-if="props.hasCode" class="field"><span>Código *</span><input v-model="form.code" maxlength="60" required></label>
        <label class="field"><span>Nome *</span><input v-model="form.name" maxlength="200" required></label>
        <div class="catalog-form-actions">
          <button type="button" class="btn small" @click="cancel"><X :size="13" /> Cancelar</button>
          <button type="submit" class="btn small primary" :disabled="saving">
            <Check :size="13" /> {{ saving ? "Salvando..." : "Salvar" }}
          </button>
        </div>
        <p v-if="formError" class="catalog-error" role="alert">{{ formError }}</p>
      </form>

      <p v-if="loading" class="catalog-hint"><span class="spinner spinner-small" /> Carregando...</p>
      <p v-else-if="error" class="catalog-error" role="alert">{{ error }}</p>
      <p v-else-if="items.length === 0" class="catalog-hint" data-testid="catalog-empty">
        Nenhum registro cadastrado.
      </p>
      <ul v-else class="catalog-list">
        <li v-for="item in items" :key="item.id" :data-testid="`catalog-item-${item.id}`">
          <span class="catalog-name">
            <strong v-if="item.code">{{ item.code }}</strong>{{ item.name }}
          </span>
          <span class="catalog-actions">
            <span class="status" :class="item.active ? 'status--on' : 'status--off'">
              {{ item.active ? "Ativo" : "Inativo" }}
            </span>
            <button type="button" class="text-button" :disabled="saving" @click="startEdit(item)">
              <Pencil :size="12" /> Editar
            </button>
            <button type="button" class="text-button" :disabled="saving" @click="toggleActive(item)">
              {{ item.active ? "Desativar" : "Reativar" }}
            </button>
          </span>
        </li>
      </ul>
    </template>
  </section>
</template>

<style scoped>
.catalog { display: grid; gap: 10px; padding: 4px 0 14px; }
.catalog-header { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.catalog-header h3 { margin: 0; color: #2b3e58; font-size: 13px; font-weight: 800; }
.catalog-hint { display: flex; align-items: center; gap: 8px; margin: 0; color: #8b96a5; font-size: 12px; }
.catalog-error { margin: 0; color: #a4453a; font-size: 12px; font-weight: 700; }
.catalog-form { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; border: 1px solid #e4e9f0; border-radius: 10px; padding: 12px; background: #f8fafc; }
.catalog-form-actions { display: flex; grid-column: 1 / -1; justify-content: flex-end; gap: 8px; }
.catalog-form .catalog-error { grid-column: 1 / -1; }
.catalog-list { display: grid; margin: 0; padding: 0; gap: 2px; list-style: none; }
.catalog-list li { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 8px 12px; border-bottom: 1px solid #f0f3f7; padding: 7px 2px; }
.catalog-list li:last-child { border-bottom: 0; }
.catalog-name { display: flex; min-width: 0; flex: 1 1 200px; align-items: center; gap: 7px; color: #2b3e58; font-size: 12.5px; }
.catalog-name strong { border-radius: 5px; background: #eef2f7; padding: 2px 6px; color: #53647a; font-size: 10.5px; }
.catalog-actions { display: flex; flex: 0 0 auto; align-items: center; gap: 10px; }
.status { border-radius: 999px; padding: 3px 8px; font-size: 10.5px; font-weight: 750; }
.status--on { background: #eaf4e5; color: #477a32; }
.status--off { background: #eef2f7; color: #6b7a8f; }
.text-button { display: inline-flex; align-items: center; gap: 4px; border: 0; padding: 2px; background: transparent; color: #304f7e; font-size: 11.5px; font-weight: 750; }
.spinner-small { width: 14px; height: 14px; border-width: 2px; }
@media (max-width: 620px) { .catalog-form { grid-template-columns: 1fr; } }
</style>
