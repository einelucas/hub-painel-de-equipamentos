<script setup lang="ts">
import { computed, ref } from "vue";
import { RefreshCw, Trash2 } from "lucide-vue-next";
import Button from "~/components/ui/Button.vue";
import SupplierLinkModal, { type SupplierLinkValues } from "~/components/equipment/SupplierLinkModal.vue";
import type { CatalogList, EquipmentSupplier, Supplier } from "~/types/equipment";
import { formatDateTime } from "~/utils/format";

const props = defineProps<{ equipmentId: string }>();
const api = useApi();
const auth = useAuthStore();

const links = ref<EquipmentSupplier[]>([]);
const catalog = ref<Supplier[]>([]);
const loading = ref(true);
const busy = ref(false);
const error = ref("");
const actionError = ref("");
const showLink = ref(false);
const opening = ref(false);
let loadingNow = false;

const canWrite = computed(() => auth.can("suppliers:write"));
const current = computed<EquipmentSupplier | null>(
  () => links.value.find((item) => item.endedAt === null) ?? null,
);
const history = computed(() => links.value.filter((item) => item.endedAt !== null));
const available = computed(() =>
  catalog.value.filter((item) => item.id !== current.value?.supplier.id),
);

async function load(): Promise<void> {
  if (loadingNow) return;
  loadingNow = true;
  loading.value = true;
  error.value = "";
  try {
    links.value = (
      await api.get<CatalogList<EquipmentSupplier>>(`/equipments/${props.equipmentId}/suppliers`)
    ).items;
  } catch (caught) {
    error.value =
      caught instanceof Error ? caught.message : "Não foi possível carregar o fornecedor.";
  } finally {
    loading.value = false;
    loadingNow = false;
  }
}

async function openLink(): Promise<void> {
  if (opening.value) return;
  opening.value = true;
  actionError.value = "";
  try {
    catalog.value = (await api.get<CatalogList<Supplier>>("/suppliers")).items;
    showLink.value = true;
  } catch (caught) {
    actionError.value =
      caught instanceof Error ? caught.message : "Não foi possível carregar os fornecedores.";
  } finally {
    opening.value = false;
  }
}

async function run(action: () => Promise<unknown>, fallback: string): Promise<void> {
  if (busy.value) return;
  busy.value = true;
  actionError.value = "";
  try {
    await action();
    await load();
  } catch (caught) {
    actionError.value = caught instanceof Error ? caught.message : fallback;
  } finally {
    busy.value = false;
  }
}

async function confirmLink(values: SupplierLinkValues): Promise<void> {
  const payload = { ...values, isPrimary: true };
  await run(
    () =>
      current.value
        ? api.put(`/equipments/${props.equipmentId}/suppliers`, payload)
        : api.post(`/equipments/${props.equipmentId}/suppliers`, payload),
    current.value
      ? "Não foi possível substituir o fornecedor."
      : "Não foi possível vincular o fornecedor.",
  );
  if (!actionError.value) showLink.value = false;
}

async function unlink(supplierId: string): Promise<void> {
  await run(
    () => api.delete(`/equipments/${props.equipmentId}/suppliers/${supplierId}`),
    "Não foi possível desvincular o fornecedor.",
  );
}

onMounted(load);
</script>

<template>
  <section class="surface">
    <div class="surface-header">
      <div>
        <h2>Fornecedor atual</h2>
        <p>Um equipamento pode trocar de fornecedor, mantendo no máximo um vínculo ativo por vez.</p>
      </div>
      <Button v-if="canWrite && !current" variant="default" :loading="opening" @click="openLink">
        Vincular fornecedor
      </Button>
      <Button v-else-if="canWrite" variant="outline" :disabled="busy || opening" data-testid="replace-supplier" @click="openLink">
        <RefreshCw v-if="!opening" :size="15" /> Substituir fornecedor
      </Button>
    </div>

    <div v-if="loading" class="supplier-state" data-testid="suppliers-loading" role="status">
      <span class="spinner" /> Carregando fornecedor...
    </div>
    <div v-else-if="error" class="empty-state table-empty" role="alert" data-testid="suppliers-error">
      <h2>Não foi possível carregar</h2><p>{{ error }}</p>
      <Button variant="outline" @click="load">Tentar novamente</Button>
    </div>
    <template v-else>
      <p v-if="actionError" class="notice error supplier-notice" role="alert">{{ actionError }}</p>
      <div v-if="!current" class="empty-state table-empty" data-testid="suppliers-empty">
        <h2>Nenhum fornecedor vinculado</h2>
        <p>O processo não é bloqueado por isso nesta etapa, mas é obrigatório para concluir (Fase 7 → 8).</p>
      </div>
      <div v-else class="current-supplier" data-testid="current-supplier">
        <strong>{{ current.supplier.legalName }}</strong>
        <span>Desde: {{ formatDateTime(current.startedAt) }}</span>
        <span>Fase de entrada: {{ current.startStage ?? "—" }}</span>
        <span v-if="current.role">Papel: {{ current.role }}</span>
        <button
          v-if="canWrite"
          class="text-button danger"
          :disabled="busy"
          :aria-busy="busy"
          @click="unlink(current.supplier.id)"
        >
          <span v-if="busy" class="spinner-small" aria-hidden="true" />
          <Trash2 v-else :size="13" /> {{ busy ? "Encerrando..." : "Encerrar vínculo" }}
        </button>
      </div>

      <div v-if="history.length" class="table-wrap" data-testid="supplier-history">
        <h3>Histórico de fornecedores</h3>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Fornecedor</TableHead>
              <TableHead>Período</TableHead>
              <TableHead>Fases</TableHead>
              <TableHead>Motivo</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow v-for="item in history" :key="item.id" :data-testid="`supplier-history-${item.id}`">
              <TableCell class="font-semibold">{{ item.supplier.legalName }}</TableCell>
              <TableCell>{{ formatDateTime(item.startedAt) }} → {{ formatDateTime(item.endedAt) }}</TableCell>
              <TableCell>{{ item.startStage ?? "—" }} → {{ item.endStage ?? "—" }}</TableCell>
              <TableCell>{{ item.changeReason ?? "—" }}</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </div>
    </template>

    <SupplierLinkModal
      :open="showLink"
      :current="current"
      :suppliers="available"
      :busy="busy"
      :error="actionError"
      @close="showLink = false"
      @submit="confirmLink"
    />
  </section>
</template>

<style scoped>
.supplier-state { display: flex; min-height: 160px; align-items: center; justify-content: center; gap: 12px; color: #748197; }
.supplier-notice { margin: 14px 18px 0; }
.current-supplier { display: flex; flex-wrap: wrap; gap: 8px 18px; margin: 0 18px 14px; border: 1px solid #dfe7f1; border-radius: 10px; padding: 13px; color: #53657c; font-size: 12px; }
.current-supplier strong { width: 100%; color: #213a5c; font-size: 15px; }
.table-wrap h3 { margin: 0 0 10px; color: #2b3e58; font-size: 13px; }
.table-wrap { padding: 0 18px 18px; overflow-x: auto; }
.table-empty { margin: auto; padding-bottom: 28px; }
.text-button { display: inline-flex; align-items: center; gap: 5px; border: 0; padding: 4px; background: transparent; color: #304f7e; font-size: 12px; font-weight: 750; }
.text-button.danger { color: #a4453a; }
</style>
