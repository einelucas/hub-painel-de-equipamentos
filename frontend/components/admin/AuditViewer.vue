<script setup lang="ts">
import { RefreshCw } from "lucide-vue-next";
import type { CatalogList, Equipment, EquipmentList } from "~/types/equipment";
import { formatDateTime } from "~/utils/format";
import { toOptions } from "~/utils/selectOptions";
import SearchableSelect from "~/components/ui/SearchableSelect.vue";

interface Audit {
  id: string;
  action: string;
  entity: string;
  entityId: string | null;
  previousData: unknown;
  newData: unknown;
  metadata: unknown;
  createdAt: string;
  user: { name: string; email: string } | null;
}

interface UserOption {
  id: string;
  name: string;
  email: string;
}

const api = useApi();
const items = ref<Audit[]>([]);
const loading = ref(true);
const page = ref(1);
const pages = ref(1);
const entity = ref("");
const action = ref("");
const equipmentId = ref("");
const userId = ref("");
const dateFrom = ref("");
const dateTo = ref("");
const message = ref("");
let loadVersion = 0;

// GAP-019 (Etapa 6D): opções reais para os filtros de Equipamento/Usuário —
// nenhum ID digitado à mão, sem busca avançada/query builder.
const equipmentOptions = ref<Equipment[]>([]);
const userOptions = ref<UserOption[]>([]);
const equipmentSelectOptions = computed(() => toOptions(equipmentOptions.value));
const userSelectOptions = computed(() =>
  userOptions.value.map((item) => ({ id: item.id, label: item.name, searchText: item.email })),
);

async function load() {
  const version = ++loadVersion;
  loading.value = true;
  message.value = "";
  try {
    const res = await api.get<{ items: Audit[]; pagination: { totalPages: number } }>("/auditoria", {
      page: page.value,
      pageSize: 50,
      entity: entity.value || undefined,
      action: action.value || undefined,
      equipment_id: equipmentId.value || undefined,
      user_id: userId.value || undefined,
      date_from: dateFrom.value || undefined,
      date_to: dateTo.value || undefined,
    });
    if (version !== loadVersion) return;
    items.value = res.items;
    pages.value = res.pagination.totalPages;
  } catch (cause) {
    if (version !== loadVersion) return;
    message.value = cause instanceof Error ? cause.message : "Erro ao carregar auditoria.";
  } finally {
    if (version === loadVersion) loading.value = false;
  }
}

watch([page, entity, action, equipmentId, userId, dateFrom, dateTo], load);
onMounted(async () => {
  // Opções dos filtros carregam junto da primeira página; falha nelas não bloqueia a listagem.
  const options = (async () => {
    try {
      const [equipments, users] = await Promise.all([
        api.get<EquipmentList>("/equipments", { pageSize: 100, sortBy: "name" }),
        api.get<CatalogList<UserOption>>("/usuarios"),
      ]);
      equipmentOptions.value = equipments.items;
      userOptions.value = users.items;
    } catch {
      // Filtros ficam sem opções; a listagem principal segue funcionando.
    }
  })();
  await Promise.all([options, load()]);
});
</script>

<template>
  <div class="space-y-4">
    <div class="flex flex-wrap items-end gap-3">
      <div class="space-y-1">
        <Label for="au-entity">Entidade</Label>
        <Input id="au-entity" v-model="entity" placeholder="ex.: User" @change="page = 1" />
      </div>
      <div class="space-y-1">
        <Label for="au-action">Ação</Label>
        <Input id="au-action" v-model="action" placeholder="ex.: user.update" @change="page = 1" />
      </div>
      <div class="space-y-1">
        <Label>Equipamento</Label>
        <SearchableSelect
          v-model="equipmentId"
          class="min-w-[180px]"
          :options="equipmentSelectOptions"
          label="Equipamento"
          placeholder="Buscar equipamento"
          empty-label="Todos"
          test-id="au-equipment"
          @change="page = 1"
        />
      </div>
      <div class="space-y-1">
        <Label>Usuário</Label>
        <SearchableSelect
          v-model="userId"
          class="min-w-[180px]"
          :options="userSelectOptions"
          label="Usuário"
          placeholder="Buscar usuário"
          empty-label="Todos"
          test-id="au-user"
          @change="page = 1"
        />
      </div>
      <div class="space-y-1">
        <Label for="au-date-from">De</Label>
        <Input id="au-date-from" v-model="dateFrom" type="date" @change="page = 1" />
      </div>
      <div class="space-y-1">
        <Label for="au-date-to">Até</Label>
        <Input id="au-date-to" v-model="dateTo" type="date" @change="page = 1" />
      </div>
      <Button variant="outline" size="icon" aria-label="Atualizar" :disabled="loading" :aria-busy="loading" @click="load">
        <RefreshCw class="size-4" :class="{ 'animate-spin': loading }" />
      </Button>
    </div>

    <p v-if="message" class="text-sm text-danger">{{ message }}</p>
    <div v-else-if="loading && !items.length" class="space-y-2" role="status" aria-label="Carregando auditoria">
      <SkeletonBlock :rows="6" />
    </div>

    <template v-else>
      <Table :class="loading ? 'opacity-60 transition-opacity' : ''" :aria-busy="loading">
        <TableHeader>
          <TableRow>
            <TableHead>Quando</TableHead>
            <TableHead>Usuário</TableHead>
            <TableHead>Ação</TableHead>
            <TableHead>Entidade</TableHead>
            <TableHead>Registro</TableHead>
            <TableHead>Alteração</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow v-if="!items.length">
            <TableCell colspan="6" class="py-8 text-center text-neutralbrand">
              Nenhum evento de auditoria encontrado.
            </TableCell>
          </TableRow>
          <TableRow v-for="item in items" :key="item.id">
            <TableCell>{{ formatDateTime(item.createdAt) }}</TableCell>
            <TableCell>{{ item.user?.name || item.user?.email || "sistema" }}</TableCell>
            <TableCell><Badge>{{ item.action }}</Badge></TableCell>
            <TableCell>{{ item.entity }}</TableCell>
            <TableCell>{{ item.entityId ?? "—" }}</TableCell>
            <TableCell>
              <details>
                <summary class="cursor-pointer text-sm text-primary">Visualizar</summary>
                <pre class="mt-1 max-w-xl overflow-auto text-xs">{{
                  JSON.stringify({ anterior: item.previousData, novo: item.newData, metadata: item.metadata }, null, 2)
                }}</pre>
              </details>
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>

      <div v-if="pages > 1" class="flex items-center justify-between text-sm">
        <span class="text-neutralbrand">Página {{ page }} de {{ pages }}</span>
        <div class="flex gap-2">
          <Button variant="outline" size="sm" :disabled="page <= 1" @click="page--">Anterior</Button>
          <Button variant="outline" size="sm" :disabled="page >= pages" @click="page++">Próxima</Button>
        </div>
      </div>
    </template>
  </div>
</template>
