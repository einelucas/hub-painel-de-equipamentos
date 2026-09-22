<script setup lang="ts">
import { RefreshCw } from "lucide-vue-next";
import type { CatalogList, Equipment, EquipmentList } from "~/types/equipment";
import { formatDateTime } from "~/utils/format";

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

// GAP-019 (Etapa 6D): opções reais para os filtros de Equipamento/Usuário —
// nenhum ID digitado à mão, sem busca avançada/query builder.
const equipmentOptions = ref<Equipment[]>([]);
const userOptions = ref<UserOption[]>([]);

async function load() {
  loading.value = true;
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
    items.value = res.items;
    pages.value = res.pagination.totalPages;
  } catch (cause) {
    message.value = cause instanceof Error ? cause.message : "Erro ao carregar auditoria.";
  } finally {
    loading.value = false;
  }
}

watch([page, entity, action, equipmentId, userId, dateFrom, dateTo], load);
onMounted(async () => {
  const [equipments, users] = await Promise.all([
    api.get<EquipmentList>("/equipments", { pageSize: 100, sortBy: "name" }),
    api.get<CatalogList<UserOption>>("/usuarios"),
  ]);
  equipmentOptions.value = equipments.items;
  userOptions.value = users.items;
  await load();
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
        <Label for="au-equipment">Equipamento</Label>
        <select
          id="au-equipment"
          v-model="equipmentId"
          class="flex h-9 w-full min-w-[180px] rounded-lg border border-input bg-background px-3 py-1 text-sm font-medium text-foreground shadow-sm"
          @change="page = 1"
        >
          <option value="">Todos</option>
          <option v-for="item in equipmentOptions" :key="item.id" :value="item.id">{{ item.name }}</option>
        </select>
      </div>
      <div class="space-y-1">
        <Label for="au-user">Usuário</Label>
        <select
          id="au-user"
          v-model="userId"
          class="flex h-9 w-full min-w-[180px] rounded-lg border border-input bg-background px-3 py-1 text-sm font-medium text-foreground shadow-sm"
          @change="page = 1"
        >
          <option value="">Todos</option>
          <option v-for="item in userOptions" :key="item.id" :value="item.id">{{ item.name }}</option>
        </select>
      </div>
      <div class="space-y-1">
        <Label for="au-date-from">De</Label>
        <Input id="au-date-from" v-model="dateFrom" type="date" @change="page = 1" />
      </div>
      <div class="space-y-1">
        <Label for="au-date-to">Até</Label>
        <Input id="au-date-to" v-model="dateTo" type="date" @change="page = 1" />
      </div>
      <Button variant="outline" size="icon" aria-label="Atualizar" @click="load">
        <RefreshCw class="size-4" />
      </Button>
    </div>

    <p v-if="message" class="text-sm text-danger">{{ message }}</p>
    <p v-else-if="loading" class="text-sm text-neutralbrand">Carregando…</p>

    <template v-else>
      <Table>
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
