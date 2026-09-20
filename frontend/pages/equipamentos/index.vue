<script setup lang="ts">
import { Plus, Search } from "lucide-vue-next";
import type { CatalogItem, CatalogList, Equipment, EquipmentList, Pagination } from "~/types/equipment";
import { EQUIPMENT_STAGES } from "~/utils/stages";

definePageMeta({ middleware: "auth" });
const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const api = useApi();
const context = useModuleContextStore();

const equipments = ref<Equipment[]>([]);
const pagination = ref<Pagination | null>(null);
const disciplines = ref<CatalogItem[]>([]);
const search = ref("");
const stage = ref<string>("");
const disciplineId = ref("");
const page = ref(1);
const loading = ref(true);
const refreshing = ref(false);
const error = ref("");
const showForm = ref(false);
let requestVersion = 0;

const allowed = computed(() => auth.can("equipments:read"));
const canCreate = computed(() => auth.can("equipments:write") && Boolean(context.selectedUnit));

async function syncQuery(): Promise<void> {
  const query: Record<string, string> = { ...(route.query as Record<string, string>) };
  if (context.selectedUnit) query.unit = context.selectedUnit;
  else delete query.unit;
  if (context.selectedEquipment) query.equipment = context.selectedEquipment;
  else delete query.equipment;
  await router.replace({ query });
}

async function load(): Promise<void> {
  const version = ++requestVersion;
  refreshing.value = true;
  error.value = "";
  try {
    const query: Record<string, unknown> = {
      ...context.apiQuery,
      page: page.value,
      pageSize: 25,
      sortBy: "name",
    };
    if (search.value.trim()) query.search = search.value.trim();
    if (stage.value !== "") query.stage = Number(stage.value);
    if (disciplineId.value) query.discipline_id = disciplineId.value;
    const result = await api.get<EquipmentList>("/equipments", query);
    if (version !== requestVersion) return;
    equipments.value = result.items;
    pagination.value = result.pagination;
  } catch (caught) {
    if (version !== requestVersion) return;
    error.value = caught instanceof Error ? caught.message : "Não foi possível carregar os equipamentos.";
    equipments.value = [];
    pagination.value = null;
  } finally {
    if (version === requestVersion) {
      refreshing.value = false;
      loading.value = false;
    }
  }
}

async function reload(): Promise<void> {
  page.value = 1;
  await syncQuery();
  await load();
}

async function saved(_equipment: Equipment): Promise<void> {
  showForm.value = false;
  await context.loadEquipmentOptions();
  await load();
}

onMounted(async () => {
  if (!allowed.value) {
    loading.value = false;
    return;
  }
  await context.initialize({
    unit: typeof route.query.unit === "string" ? route.query.unit : undefined,
    equipment: typeof route.query.equipment === "string" ? route.query.equipment : undefined,
  });
  disciplines.value = (await api.get<CatalogList<CatalogItem>>("/disciplines")).items;
  await syncQuery();
  await load();
});
</script>

<template>
  <ModuleWorkspace
    eyebrow="Planejamento · Equipamentos"
    title="Equipamentos"
    description="Listagem operacional com busca, filtros e acesso ao detalhe do processo."
  >
    <div v-if="!allowed" class="surface empty-state state-card" role="alert">
      <h2>Sem permissão</h2><p>Seu perfil não tem acesso à leitura de equipamentos.</p>
    </div>
    <div v-else class="stack">
      <ModuleFilters :refreshing="refreshing" @change="reload">
        <form class="field" @submit.prevent="reload">
          <span>Busca</span>
          <div class="search-control">
            <input v-model="search" placeholder="Nome do equipamento">
            <button class="btn" type="submit"><Search :size="16" /> Buscar</button>
          </div>
        </form>
        <template #actions>
          <button
            v-if="auth.can('equipments:write')"
            class="btn primary"
            :disabled="!canCreate"
            :title="!context.selectedUnit ? 'Selecione uma unidade para cadastrar' : undefined"
            @click="showForm = true"
          >
            <Plus :size="16" /> Novo equipamento
          </button>
        </template>
      </ModuleFilters>

      <section class="surface">
        <div class="surface-header">
          <div><h2>Resultados</h2><p>{{ pagination?.total ?? 0 }} registro(s) encontrado(s).</p></div>
        </div>
        <div class="table-filters">
          <label class="inline-field">
            <span>Etapa</span>
            <select v-model="stage" @change="reload">
              <option value="">Todas</option>
              <option v-for="(name, index) in EQUIPMENT_STAGES" :key="name" :value="String(index)">{{ index }} · {{ name }}</option>
            </select>
          </label>
          <label class="inline-field">
            <span>Disciplina</span>
            <select v-model="disciplineId" @change="reload">
              <option value="">Todas</option>
              <option v-for="item in disciplines" :key="item.id" :value="item.id">{{ item.name }}</option>
            </select>
          </label>
        </div>

        <div v-if="loading" class="queue-state"><span class="spinner" /> Carregando equipamentos...</div>
        <div v-else-if="error" class="empty-state table-empty" role="alert">
          <h2>Não foi possível carregar</h2><p>{{ error }}</p>
          <button class="btn" @click="load">Tentar novamente</button>
        </div>
        <template v-else>
          <EquipmentTable :equipments="equipments" />
          <div v-if="pagination && pagination.totalPages > 1" class="pagination">
            <button class="btn small" :disabled="page <= 1" @click="page -= 1; load()">Anterior</button>
            <span>Página {{ page }} de {{ pagination.totalPages }}</span>
            <button class="btn small" :disabled="page >= pagination.totalPages" @click="page += 1; load()">Próxima</button>
          </div>
        </template>
      </section>
    </div>

    <AppModal :open="showForm" title="Novo equipamento" @close="showForm = false">
      <EquipmentForm v-if="showForm && context.selectedUnit" :unit-id="context.selectedUnit" @saved="saved" @cancel="showForm = false" />
    </AppModal>
  </ModuleWorkspace>
</template>

<style scoped>
.state-card { max-width: none; }
.search-control { display: flex; gap: 7px; }
.table-filters { display: flex; flex-wrap: wrap; gap: 14px; padding: 14px 18px 0; }
.table-filters select { min-width: 190px; }
.inline-field { display: grid; gap: 4px; }
.inline-field > span { color: #7a879a; font-size: 10px; font-weight: 800; letter-spacing: .05em; text-transform: uppercase; }
.queue-state { display: flex; min-height: 220px; align-items: center; justify-content: center; gap: 12px; color: #748197; }
.table-empty { margin: auto; padding-bottom: 28px; }
.pagination { display: flex; align-items: center; justify-content: flex-end; gap: 12px; padding: 0 18px 18px; color: #68778c; font-size: 12px; }
</style>
