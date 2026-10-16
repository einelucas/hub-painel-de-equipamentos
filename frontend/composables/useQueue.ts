import type { Pagination, QueueList } from "~/types/equipment";

export type QueueEndpoint = "engineering" | "legal" | "procurement";

/** Carrega uma fila operacional respeitando os filtros globais do módulo. */
export function useQueue<T>(endpoint: QueueEndpoint) {
  const api = useApi();
  const route = useRoute();
  const router = useRouter();
  const context = useModuleContextStore();
  const items = ref<T[]>([]) as Ref<T[]>;
  const pagination = ref<Pagination | null>(null);
  const search = ref("");
  const page = ref(1);
  const loading = ref(true);
  const refreshing = ref(false);
  const error = ref("");
  // Filtros específicos da fila (ex.: `discipline_id` na Engenharia),
  // opcionais e fora dos globais de Unidade/Equipamento. Chaves em
  // snake_case, como o restante da query desta store.
  const filters = reactive<Record<string, string>>({});
  let requestVersion = 0;

  async function load(): Promise<void> {
    const version = ++requestVersion;
    refreshing.value = true;
    error.value = "";
    try {
      const query: Record<string, unknown> = {
        ...context.apiQuery,
        page: page.value,
        pageSize: 25,
      };
      if (search.value.trim()) query.search = search.value.trim();
      for (const [key, value] of Object.entries(filters)) {
        if (value) query[key] = value;
      }
      const result = await api.get<QueueList<T>>(`/queues/${endpoint}`, query);
      if (version !== requestVersion) return;
      items.value = result.items;
      pagination.value = result.pagination;
    } catch (caught) {
      if (version !== requestVersion) return;
      error.value = caught instanceof Error ? caught.message : "Não foi possível carregar a fila.";
      items.value = [];
      pagination.value = null;
    } finally {
      if (version === requestVersion) {
        refreshing.value = false;
        loading.value = false;
      }
    }
  }

  async function syncQuery(): Promise<void> {
    const query: Record<string, string> = { ...(route.query as Record<string, string>) };
    if (context.selectedUnit) query.unit = context.selectedUnit;
    else delete query.unit;
    if (context.selectedProjectContext) query.project = context.selectedProjectContext;
    else delete query.project;
    if (context.selectedEquipment) query.equipment = context.selectedEquipment;
    else delete query.equipment;
    await router.replace({ query });
  }

  async function initialize(query: { unit?: string; project?: string; equipment?: string }): Promise<void> {
    loading.value = true;
    await context.initialize(query);
    await syncQuery();
    await load();
  }

  async function reload(): Promise<void> {
    page.value = 1;
    await syncQuery();
    await load();
  }

  async function goToPage(next: number): Promise<void> {
    page.value = next;
    await load();
  }

  return {
    items,
    pagination,
    search,
    page,
    filters,
    loading,
    refreshing,
    error,
    initialize,
    syncQuery,
    load,
    reload,
    goToPage,
  };
}
