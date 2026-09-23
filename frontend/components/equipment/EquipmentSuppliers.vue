<script setup lang="ts">
import { computed, ref } from "vue";
import { RefreshCw, Trash2 } from "lucide-vue-next";
import type { CatalogList, EquipmentSupplier, Supplier } from "~/types/equipment";

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
const chosen = ref("");
const role = ref("");

const canWrite = computed(() => auth.can("suppliers:write"));
/** Etapa 7A: no máximo um fornecedor por equipamento. */
const current = computed<EquipmentSupplier | null>(() => links.value[0] ?? null);
const available = computed(() =>
  catalog.value.filter((item) => item.id !== current.value?.supplier.id),
);

async function load(): Promise<void> {
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
  }
}

async function openLink(): Promise<void> {
  actionError.value = "";
  chosen.value = "";
  role.value = "";
  showLink.value = true;
  catalog.value = (await api.get<CatalogList<Supplier>>("/suppliers")).items;
}

async function run(action: () => Promise<unknown>, fallback: string): Promise<void> {
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

async function confirmLink(): Promise<void> {
  if (!chosen.value) return;
  const payload = { supplierId: chosen.value, role: role.value.trim() || null, isPrimary: true };
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
        <h2>Fornecedor</h2>
        <p>Etapa 7A: um equipamento tem no máximo um fornecedor vinculado — todos os contratos usam este mesmo fornecedor.</p>
      </div>
      <button v-if="canWrite && !current" class="btn primary" :disabled="busy" @click="openLink">
        Vincular fornecedor
      </button>
      <button v-else-if="canWrite" class="btn" :disabled="busy" data-testid="replace-supplier" @click="openLink">
        <RefreshCw :size="15" /> Substituir fornecedor
      </button>
    </div>

    <div v-if="loading" class="supplier-state" data-testid="suppliers-loading">
      <span class="spinner" /> Carregando fornecedor...
    </div>
    <div v-else-if="error" class="empty-state table-empty" role="alert" data-testid="suppliers-error">
      <h2>Não foi possível carregar</h2><p>{{ error }}</p>
      <button class="btn" @click="load">Tentar novamente</button>
    </div>
    <template v-else>
      <p v-if="actionError" class="notice error supplier-notice" role="alert">{{ actionError }}</p>
      <div v-if="!current" class="empty-state table-empty" data-testid="suppliers-empty">
        <h2>Nenhum fornecedor vinculado</h2>
        <p>O processo não é bloqueado por isso nesta etapa, mas é obrigatório para concluir (Fase 7 → 8).</p>
      </div>
      <div v-else class="table-wrap">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Fornecedor</TableHead>
              <TableHead>Nome fantasia</TableHead>
              <TableHead>Documento</TableHead>
              <TableHead>Papel</TableHead>
              <TableHead />
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow :data-testid="`supplier-${current.supplier.id}`">
              <TableCell class="font-semibold">{{ current.supplier.legalName }}</TableCell>
              <TableCell>{{ current.supplier.tradeName ?? "—" }}</TableCell>
              <TableCell>{{ current.supplier.taxId ?? "—" }}</TableCell>
              <TableCell>{{ current.role ?? "—" }}</TableCell>
              <TableCell>
                <button
                  v-if="canWrite"
                  class="text-button danger"
                  :disabled="busy"
                  @click="unlink(current.supplier.id)"
                >
                  <Trash2 :size="13" /> Desvincular
                </button>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </div>
    </template>

    <AppModal :open="showLink" :title="current ? 'Substituir fornecedor' : 'Vincular fornecedor'" @close="showLink = false">
      <form class="link-form" @submit.prevent="confirmLink">
        <p v-if="current" class="link-hint">
          O vínculo atual com <strong>{{ current.supplier.legalName }}</strong> será substituído.
        </p>
        <label class="field">
          <span>Fornecedor *</span>
          <select v-model="chosen" required>
            <option value="">Selecione</option>
            <option v-for="item in available" :key="item.id" :value="item.id">
              {{ item.legalName }}
            </option>
          </select>
        </label>
        <p v-if="available.length === 0" class="link-hint">
          Nenhum fornecedor disponível. Cadastre um em
          <NuxtLink to="/fornecedores">Fornecedores</NuxtLink>.
        </p>
        <label class="field"><span>Papel</span><input v-model="role" maxlength="80" placeholder="Opcional"></label>
        <p v-if="actionError" class="notice error" role="alert">{{ actionError }}</p>
        <div class="form-actions">
          <button type="button" class="btn" @click="showLink = false">Cancelar</button>
          <button type="submit" class="btn primary" :disabled="!chosen || busy">
            {{ current ? "Substituir" : "Vincular" }}
          </button>
        </div>
      </form>
    </AppModal>
  </section>
</template>

<style scoped>
.supplier-state { display: flex; min-height: 160px; align-items: center; justify-content: center; gap: 12px; color: #748197; }
.supplier-notice { margin: 14px 18px 0; }
.table-wrap { padding: 0 18px 18px; overflow-x: auto; }
.table-empty { margin: auto; padding-bottom: 28px; }
.text-button { display: inline-flex; align-items: center; gap: 5px; border: 0; padding: 4px; background: transparent; color: #304f7e; font-size: 12px; font-weight: 750; }
.text-button.danger { color: #a4453a; }
.link-form { display: grid; gap: 14px; }
.link-hint { margin: -6px 0 0; color: #8b96a5; font-size: 11.5px; }
.form-actions { display: flex; justify-content: flex-end; gap: 9px; }
</style>
