<script setup lang="ts">
import { computed, ref } from "vue";
import { Plus } from "lucide-vue-next";
import type { PurchaseOrder } from "~/types/equipment";
import { blankToNull } from "~/utils/workflow";
import EquipmentPurchaseOrdersTable from "~/components/equipment/purchase-orders/EquipmentPurchaseOrdersTable.vue";
import EquipmentPurchaseOrderForm, {
  type EquipmentPurchaseOrderFormValues,
} from "~/components/equipment/purchase-orders/EquipmentPurchaseOrderForm.vue";

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

const sorted = computed(() => [...props.items].sort((a, b) => a.createdAt.localeCompare(b.createdAt)));

function openCreate(): void {
  editing.value = null;
  actionError.value = "";
  showForm.value = true;
}

function openEdit(item: PurchaseOrder): void {
  editing.value = item;
  actionError.value = "";
  showForm.value = true;
}

function closeForm(): void {
  showForm.value = false;
  editing.value = null;
}

async function submit(values: EquipmentPurchaseOrderFormValues): Promise<void> {
  busy.value = true;
  actionError.value = "";
  const payload = {
    orderNumber: blankToNull(values.orderNumber),
    orderedAt: blankToNull(values.orderedAt),
    amount: values.amount === "" ? null : Number(values.amount),
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

    <EquipmentPurchaseOrdersTable
      :items="sorted"
      :editable="editable"
      :busy="busy"
      @edit="openEdit"
      @delete="removeItem"
    />

    <AppModal :open="showForm" :title="editing ? 'Editar ordem de compra' : 'Nova ordem de compra'" @close="closeForm">
      <EquipmentPurchaseOrderForm
        :item="editing"
        :busy="busy"
        :error="actionError"
        @submit="submit"
        @cancel="closeForm"
      />
    </AppModal>
  </section>
</template>

<style scoped>
.list-notice { margin: 0 18px 14px; }
</style>
