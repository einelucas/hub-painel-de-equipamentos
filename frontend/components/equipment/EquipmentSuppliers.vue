<script setup lang="ts">
import {
  mdiBriefcaseOutline,
  mdiCalendarOutline,
  mdiDomain,
  mdiFlagOutline,
  mdiRefresh,
  mdiTrashCanOutline,
} from "@mdi/js";
import { computed, nextTick, ref } from "vue";
import { VBtn, VChip, VIcon } from "vuetify/components";
import SupplierLinkModal, { type SupplierLinkValues } from "~/components/equipment/SupplierLinkModal.vue";
import { useConfirm } from "~/composables/useConfirm";
import type { CatalogList, EquipmentSupplier, Supplier } from "~/types/equipment";
import { formatDateTime } from "~/utils/format";

const props = defineProps<{ equipmentId: string }>();
const api = useApi();
const auth = useAuthStore();
const { confirm } = useConfirm();

const links = ref<EquipmentSupplier[]>([]);
const catalog = ref<Supplier[]>([]);
const loading = ref(true);
const busy = ref(false);
const error = ref("");
const actionError = ref("");
const showLink = ref(false);
const opening = ref(false);
const catalogLoading = ref(false);
const catalogLoaded = ref(false);
const catalogError = ref("");
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

async function loadCatalog(): Promise<void> {
  if (catalogLoading.value || catalogLoaded.value) return;
  catalogLoading.value = true;
  catalogError.value = "";
  try {
    catalog.value = (await api.get<CatalogList<Supplier>>("/suppliers")).items;
    catalogLoaded.value = true;
  } catch (caught) {
    catalogError.value =
      caught instanceof Error ? caught.message : "Não foi possível carregar os fornecedores.";
  } finally {
    catalogLoading.value = false;
  }
}

async function openLink(): Promise<void> {
  if (opening.value) return;
  opening.value = true;
  actionError.value = "";
  await nextTick();
  // O primeiro frame pinta o spinner. O modal só é montado no frame seguinte,
  // evitando que seu custo de renderização bloqueie o feedback do botão.
  await new Promise<void>((resolve) => {
    requestAnimationFrame(() => requestAnimationFrame(() => resolve()));
  });
  showLink.value = true;
  void loadCatalog();
}

function closeLink(): void {
  showLink.value = false;
  opening.value = false;
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

async function requestUnlink(link: EquipmentSupplier): Promise<void> {
  if (busy.value) return;
  const accepted = await confirm({
    title: "Encerrar vínculo",
    message: `Deseja encerrar o vínculo com “${link.supplier.legalName}”?`,
    detail:
      "O fornecedor será movido para o histórico e o equipamento ficará sem fornecedor ativo. Pode ser necessário vincular outro fornecedor para concluir o processo.",
    confirmLabel: "Encerrar vínculo",
    cancelLabel: "Manter vínculo",
    tone: "danger",
    icon: "warning",
  });
  if (accepted) await unlink(link.supplier.id);
}

onMounted(() => {
  void load();
  if (canWrite.value) void loadCatalog();
});
</script>

<template>
  <section class="surface">
    <div class="surface-header">
      <div>
        <h2>Fornecedor atual</h2>
        <p>Um equipamento pode trocar de fornecedor, mantendo no máximo um vínculo ativo por vez.</p>
      </div>
      <VBtn v-if="canWrite && !current" variant="tonal" color="primary" :loading="opening" :disabled="busy || opening" @click="openLink">
        Vincular fornecedor
      </VBtn>
      <VBtn v-else-if="canWrite" variant="outlined" color="secondary" :loading="opening" :disabled="busy || opening" data-testid="replace-supplier" :prepend-icon="!opening ? mdiRefresh : undefined" @click="openLink">
         Substituir fornecedor
      </VBtn>
    </div>

    <div v-if="loading" class="supplier-state" data-testid="suppliers-loading" role="status">
      <span class="spinner" /> Carregando fornecedor...
    </div>
    <div v-else-if="error" class="empty-state table-empty" role="alert" data-testid="suppliers-error">
      <h2>Não foi possível carregar</h2><p>{{ error }}</p>
      <VBtn variant="outlined" @click="load">Tentar novamente</VBtn>
    </div>
    <template v-else>
      <VAlert v-if="actionError" class="supplier-notice" type="error" role="alert">{{ actionError }}</VAlert>
      <div v-if="!current" class="empty-state table-empty" data-testid="suppliers-empty">
        <h2>Nenhum fornecedor vinculado</h2>
        <p>O processo não é bloqueado por isso nesta etapa, mas é obrigatório para concluir (Fase 7 → 8).</p>
      </div>
      <div v-else class="current-supplier" data-testid="current-supplier">
        <div class="supplier-identity">
          <span class="supplier-avatar" aria-hidden="true">
            <VIcon :icon="mdiDomain" size="22" />
          </span>
          <div class="supplier-name">
            <span>Fornecedor vinculado</span>
            <strong>{{ current.supplier.legalName }}</strong>
            <small v-if="current.supplier.tradeName">{{ current.supplier.tradeName }}</small>
          </div>
          <VChip class="supplier-status" color="success" variant="tonal" size="small">
            Vínculo ativo
          </VChip>
        </div>

        <dl class="supplier-details">
          <div>
            <dt><VIcon :icon="mdiCalendarOutline" size="16" /> Vinculado desde</dt>
            <dd>{{ formatDateTime(current.startedAt) }}</dd>
          </div>
          <div>
            <dt><VIcon :icon="mdiFlagOutline" size="16" /> Fase de entrada</dt>
            <dd>{{ current.startStage ?? "—" }}</dd>
          </div>
          <div>
            <dt><VIcon :icon="mdiBriefcaseOutline" size="16" /> Papel</dt>
            <dd>{{ current.role ?? "Não informado" }}</dd>
          </div>
        </dl>

        <div v-if="canWrite" class="supplier-actions">
          <p>Ao encerrar, este vínculo continuará disponível no histórico.</p>
          <VBtn
            :disabled="busy"
            :loading="busy"
            variant="tonal"
            color="error"
            size="small"
            :prepend-icon="!busy ? mdiTrashCanOutline : undefined"
            data-testid="unlink-supplier"
            @click="requestUnlink(current)"
          >
            {{ busy ? "Encerrando..." : "Encerrar vínculo" }}
          </VBtn>
        </div>
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
      :loading="catalogLoading"
      :error="actionError || catalogError"
      @close="closeLink"
      @opened="opening = false"
      @submit="confirmLink"
    />
  </section>
</template>

<style scoped>
.supplier-state { display: flex; min-height: 160px; align-items: center; justify-content: center; gap: 12px; color: #748197; }
.supplier-notice { margin: 14px 18px 0; }
.current-supplier { display: grid; gap: 16px; margin: 0 18px 18px; border: 1px solid #dfe7f1; border-radius: 12px; padding: 16px; background: linear-gradient(180deg, #fff 0%, #fbfcfe 100%); color: #53657c; }
.supplier-identity { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; align-items: center; gap: 12px; }
.supplier-avatar { display: grid; width: 42px; height: 42px; place-items: center; border-radius: 10px; background: #edf3fb; color: #304f7e; }
.supplier-name { display: grid; min-width: 0; gap: 2px; }
.supplier-name > span { color: #7a879a; font-size: 10px; font-weight: 750; letter-spacing: .06em; text-transform: uppercase; }
.supplier-name strong { overflow: hidden; color: #213a5c; font-size: 15px; text-overflow: ellipsis; white-space: nowrap; }
.supplier-name small { color: #6b7a8f; font-size: 11px; }
.supplier-status { font-weight: 700; }
.supplier-details { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin: 0; }
.supplier-details > div { display: grid; gap: 5px; min-width: 0; border: 1px solid #e5ebf2; border-radius: 9px; padding: 10px 12px; background: #fff; }
.supplier-details dt { display: flex; align-items: center; gap: 6px; color: #7a879a; font-size: 10px; font-weight: 700; text-transform: uppercase; }
.supplier-details dd { margin: 0; color: #2b3e58; font-size: 12px; font-weight: 650; }
.supplier-actions { display: flex; align-items: center; justify-content: space-between; gap: 14px; border-top: 1px solid #e5ebf2; padding-top: 13px; }
.supplier-actions p { margin: 0; color: #7a879a; font-size: 11.5px; }
.table-wrap h3 { margin: 0 0 10px; color: #2b3e58; font-size: 13px; }
.table-wrap { padding: 0 18px 18px; overflow-x: auto; }
.table-empty { margin: auto; padding-bottom: 28px; }
@media (max-width: 700px) {
  .supplier-identity { grid-template-columns: auto minmax(0, 1fr); }
  .supplier-status { grid-column: 2; justify-self: start; }
  .supplier-details { grid-template-columns: 1fr; }
  .supplier-actions { align-items: stretch; flex-direction: column; }
}
</style>
