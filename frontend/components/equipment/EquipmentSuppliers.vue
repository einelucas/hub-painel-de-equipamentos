<script setup lang="ts">
import { computed, ref } from "vue";
import { Plus, Star, Trash2 } from "lucide-vue-next";
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
const asPrimary = ref(false);

const canWrite = computed(() => auth.can("suppliers:write"));
const linkedIds = computed(() => new Set(links.value.map((item) => item.supplier.id)));
const available = computed(() => catalog.value.filter((item) => !linkedIds.value.has(item.id)));

async function load(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    links.value = (
      await api.get<CatalogList<EquipmentSupplier>>(`/equipments/${props.equipmentId}/suppliers`)
    ).items;
  } catch (caught) {
    error.value =
      caught instanceof Error ? caught.message : "Não foi possível carregar os fornecedores.";
  } finally {
    loading.value = false;
  }
}

async function openLink(): Promise<void> {
  actionError.value = "";
  chosen.value = "";
  role.value = "";
  asPrimary.value = false;
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
  await run(
    () =>
      api.post(`/equipments/${props.equipmentId}/suppliers`, {
        supplierId: chosen.value,
        role: role.value.trim() || null,
        isPrimary: asPrimary.value,
      }),
    "Não foi possível vincular o fornecedor.",
  );
  if (!actionError.value) showLink.value = false;
}

async function makePrimary(supplierId: string): Promise<void> {
  await run(
    () =>
      api.patch(`/equipments/${props.equipmentId}/suppliers/${supplierId}`, { isPrimary: true }),
    "Não foi possível definir o fornecedor principal.",
  );
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
        <h2>Fornecedores</h2>
        <p>Vínculos do equipamento. O principal aparece na fila de Suprimentos.</p>
      </div>
      <button v-if="canWrite" class="btn primary" :disabled="busy" @click="openLink">
        <Plus :size="15" /> Vincular fornecedor
      </button>
    </div>

    <div v-if="loading" class="supplier-state" data-testid="suppliers-loading">
      <span class="spinner" /> Carregando fornecedores...
    </div>
    <div v-else-if="error" class="empty-state table-empty" role="alert" data-testid="suppliers-error">
      <h2>Não foi possível carregar</h2><p>{{ error }}</p>
      <button class="btn" @click="load">Tentar novamente</button>
    </div>
    <template v-else>
      <p v-if="actionError" class="notice error supplier-notice" role="alert">{{ actionError }}</p>
      <div v-if="links.length === 0" class="empty-state table-empty" data-testid="suppliers-empty">
        <h2>Nenhum fornecedor vinculado</h2>
        <p>O processo não é bloqueado por isso nesta etapa.</p>
      </div>
      <div v-else class="table-wrap">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Fornecedor</TableHead>
              <TableHead>Nome fantasia</TableHead>
              <TableHead>Documento</TableHead>
              <TableHead>Papel</TableHead>
              <TableHead>Principal</TableHead>
              <TableHead />
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow v-for="link in links" :key="link.supplier.id" :data-testid="`supplier-${link.supplier.id}`">
              <TableCell class="font-semibold">{{ link.supplier.legalName }}</TableCell>
              <TableCell>{{ link.supplier.tradeName ?? "—" }}</TableCell>
              <TableCell>{{ link.supplier.taxId ?? "—" }}</TableCell>
              <TableCell>{{ link.role ?? "—" }}</TableCell>
              <TableCell>
                <span v-if="link.isPrimary" class="primary-badge" data-testid="primary-badge">
                  <Star :size="12" /> Principal
                </span>
                <button
                  v-else-if="canWrite"
                  class="text-button"
                  :disabled="busy"
                  @click="makePrimary(link.supplier.id)"
                >
                  Definir como principal
                </button>
                <span v-else>—</span>
              </TableCell>
              <TableCell>
                <button
                  v-if="canWrite"
                  class="text-button danger"
                  :disabled="busy"
                  @click="unlink(link.supplier.id)"
                >
                  <Trash2 :size="13" /> Desvincular
                </button>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </div>
    </template>

    <AppModal :open="showLink" title="Vincular fornecedor" @close="showLink = false">
      <form class="link-form" @submit.prevent="confirmLink">
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
        <label class="field field-check">
          <input v-model="asPrimary" type="checkbox"><span>Definir como principal</span>
        </label>
        <p v-if="actionError" class="notice error" role="alert">{{ actionError }}</p>
        <div class="form-actions">
          <button type="button" class="btn" @click="showLink = false">Cancelar</button>
          <button type="submit" class="btn primary" :disabled="!chosen || busy">Vincular</button>
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
.primary-badge { display: inline-flex; align-items: center; gap: 5px; border-radius: 999px; background: #eaf4e5; padding: 4px 9px; color: #477a32; font-size: 11px; font-weight: 750; }
.text-button { display: inline-flex; align-items: center; gap: 5px; border: 0; padding: 4px; background: transparent; color: #304f7e; font-size: 12px; font-weight: 750; }
.text-button.danger { color: #a4453a; }
.link-form { display: grid; gap: 14px; }
.link-hint { margin: -6px 0 0; color: #8b96a5; font-size: 11.5px; }
.field-check { display: flex; align-items: center; gap: 8px; }
.field-check input { width: 15px; height: 15px; }
.form-actions { display: flex; justify-content: flex-end; gap: 9px; }
</style>
