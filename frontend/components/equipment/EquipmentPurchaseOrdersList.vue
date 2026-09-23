<script setup lang="ts">
import { computed, reactive, ref } from "vue";
import { Pencil, Plus, Trash2 } from "lucide-vue-next";
import type { PurchaseOrder } from "~/types/equipment";
import { formatCurrency, formatDateOnly } from "~/utils/format";
import { blankToNull } from "~/utils/workflow";

const props = defineProps<{
  equipmentId: string;
  items: PurchaseOrder[];
  editable: boolean;
}>();
const emit = defineEmits<{ changed: [] }>();

const api = useApi();
const busy = ref(false);
const actionError = ref("");
const showForm = ref(false);
const editing = ref<PurchaseOrder | null>(null);

const form = reactive({ orderNumber: "", orderedAt: "", amount: "" });

const sorted = computed(() => [...props.items].sort((a, b) => a.createdAt.localeCompare(b.createdAt)));

function openCreate(): void {
  editing.value = null;
  form.orderNumber = "";
  form.orderedAt = "";
  form.amount = "";
  actionError.value = "";
  showForm.value = true;
}

function openEdit(item: PurchaseOrder): void {
  editing.value = item;
  form.orderNumber = item.orderNumber ?? "";
  form.orderedAt = item.orderedAt ?? "";
  form.amount = item.amount === null ? "" : String(item.amount);
  actionError.value = "";
  showForm.value = true;
}

function closeForm(): void {
  showForm.value = false;
  editing.value = null;
}

async function submit(): Promise<void> {
  busy.value = true;
  actionError.value = "";
  const payload = {
    orderNumber: blankToNull(form.orderNumber),
    orderedAt: blankToNull(form.orderedAt),
    amount: form.amount.trim() === "" ? null : Number(form.amount),
  };
  try {
    if (editing.value) {
      await api.patch(`/equipments/${props.equipmentId}/purchase-orders/${editing.value.id}`, payload);
    } else {
      await api.post(`/equipments/${props.equipmentId}/purchase-orders`, payload);
    }
    showForm.value = false;
    emit("changed");
  } catch (caught) {
    actionError.value = caught instanceof Error ? caught.message : "Não foi possível salvar a OC.";
  } finally {
    busy.value = false;
  }
}

async function removeItem(item: PurchaseOrder): Promise<void> {
  busy.value = true;
  actionError.value = "";
  try {
    await api.delete(`/equipments/${props.equipmentId}/purchase-orders/${item.id}`);
    emit("changed");
  } catch (caught) {
    actionError.value = caught instanceof Error ? caught.message : "Não foi possível excluir a OC.";
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <section class="surface">
    <div class="surface-header">
      <div>
        <h2>Ordens de compra</h2>
        <p>Um equipamento pode ter várias OCs. O Valor Total do Projeto não é a soma automática delas.</p>
      </div>
      <button v-if="editable" class="btn primary" :disabled="busy" data-testid="add-purchase-order" @click="openCreate">
        <Plus :size="15" /> Adicionar
      </button>
    </div>

    <p v-if="actionError" class="notice error list-notice" role="alert">{{ actionError }}</p>

    <div v-if="sorted.length === 0" class="empty-state table-empty" data-testid="purchase-orders-empty">
      <h2>Nenhuma OC cadastrada</h2>
      <p>É necessária ao menos uma OC para concluir o processo (Fase 7 → 8).</p>
    </div>
    <div v-else class="table-wrap">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Número</TableHead>
            <TableHead>Data</TableHead>
            <TableHead>Valor</TableHead>
            <TableHead />
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow v-for="item in sorted" :key="item.id" :data-testid="`purchase-order-${item.id}`">
            <TableCell class="font-semibold">{{ item.orderNumber ?? "—" }}</TableCell>
            <TableCell>{{ formatDateOnly(item.orderedAt) }}</TableCell>
            <TableCell>{{ formatCurrency(item.amount) }}</TableCell>
            <TableCell class="row-actions">
              <button v-if="editable" class="text-button" @click="openEdit(item)"><Pencil :size="13" /> Editar</button>
              <button v-if="editable" class="text-button danger" :disabled="busy" @click="removeItem(item)">
                <Trash2 :size="13" /> Excluir
              </button>
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </div>

    <AppModal :open="showForm" :title="editing ? 'Editar ordem de compra' : 'Nova ordem de compra'" @close="closeForm">
      <form class="item-form" @submit.prevent="submit">
        <label class="field"><span>Número da OC</span><input v-model="form.orderNumber" maxlength="80"></label>
        <label class="field"><span>Data da OC</span><input v-model="form.orderedAt" type="date"></label>
        <label class="field"><span>Valor</span><input v-model="form.amount" type="number" min="0" step="0.01"></label>
        <p v-if="actionError" class="notice error" role="alert">{{ actionError }}</p>
        <div class="form-actions">
          <button type="button" class="btn" @click="closeForm">Cancelar</button>
          <button type="submit" class="btn primary" :disabled="busy">{{ busy ? "Salvando..." : "Salvar" }}</button>
        </div>
      </form>
    </AppModal>
  </section>
</template>

<style scoped>
.list-notice { margin: 0 18px 14px; }
.table-wrap { padding: 0 18px 18px; overflow-x: auto; }
.table-empty { margin: auto; padding-bottom: 28px; }
.row-actions { display: flex; gap: 12px; white-space: nowrap; }
.text-button { display: inline-flex; align-items: center; gap: 5px; border: 0; padding: 4px; background: transparent; color: #304f7e; font-size: 12px; font-weight: 750; }
.text-button.danger { color: #a4453a; }
.item-form { display: grid; gap: 14px; }
.field { display: grid; gap: 4px; font-size: 12px; }
.field span { color: #7a879a; font-size: 10px; font-weight: 800; letter-spacing: .05em; text-transform: uppercase; }
.field input { border: 1px solid #d8dee7; border-radius: 6px; padding: 7px 9px; font-size: 13px; }
.form-actions { display: flex; justify-content: flex-end; gap: 9px; }
</style>
