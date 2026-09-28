<script setup lang="ts">
import { computed, ref } from "vue";
import { Plus } from "lucide-vue-next";
import type { PurchaseRequest, RequirementGroup, RequirementWaiver } from "~/types/equipment";
import { blankToNull } from "~/utils/workflow";
import EquipmentPurchaseRequestsTable from "~/components/equipment/purchase-requests/EquipmentPurchaseRequestsTable.vue";
import EquipmentPurchaseRequestForm, {
  type EquipmentPurchaseRequestFormValues,
} from "~/components/equipment/purchase-requests/EquipmentPurchaseRequestForm.vue";

const props = defineProps<{
  equipmentId: string;
  items: PurchaseRequest[];
  editable: boolean;
  /** Etapa 7.1: grupo PURCHASE_REQUEST da fase atual, quando ela exigir
   * isso para avançar — permite marcar "Não possui SC/OCI" direto aqui. */
  requirementGroup?: RequirementGroup | null;
  requirementStage?: number;
  /** Dispensa ACTIVE do grupo PURCHASE_REQUEST, independente da fase
   * atual — para continuar visível depois que o processo avança de fase. */
  requirementWaiver?: RequirementWaiver | null;
}>();
const emit = defineEmits<{ changed: [] }>();

const api = useApi();
const busy = ref(false);
const actionError = ref("");
const showForm = ref(false);
const editing = ref<PurchaseRequest | null>(null);

const sorted = computed(() => [...props.items].sort((a, b) => a.createdAt.localeCompare(b.createdAt)));

function openCreate(): void {
  editing.value = null;
  actionError.value = "";
  showForm.value = true;
}

function openEdit(item: PurchaseRequest): void {
  editing.value = item;
  actionError.value = "";
  showForm.value = true;
}

function closeForm(): void {
  showForm.value = false;
  editing.value = null;
}

async function submit(values: EquipmentPurchaseRequestFormValues): Promise<void> {
  busy.value = true;
  actionError.value = "";
  const payload = {
    kind: values.kind === "" ? null : values.kind,
    requestNumber: blankToNull(values.requestNumber),
    requestedAt: blankToNull(values.requestedAt),
  };
  try {
    if (editing.value) {
      await api.patch(`/equipments/${props.equipmentId}/purchase-requests/${editing.value.id}`, payload);
    } else {
      await api.post(`/equipments/${props.equipmentId}/purchase-requests`, payload);
    }
    showForm.value = false;
    emit("changed");
  } catch (caught) {
    actionError.value = caught instanceof Error ? caught.message : "Não foi possível salvar a SC/OCI.";
  } finally {
    busy.value = false;
  }
}

async function removeItem(item: PurchaseRequest): Promise<void> {
  busy.value = true;
  actionError.value = "";
  try {
    await api.delete(`/equipments/${props.equipmentId}/purchase-requests/${item.id}`);
    emit("changed");
  } catch (caught) {
    actionError.value = caught instanceof Error ? caught.message : "Não foi possível excluir a SC/OCI.";
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <section class="surface">
    <div class="surface-header">
      <div>
        <h2>SC / OCI</h2>
        <p>Solicitações de compra ou importação. Um equipamento pode ter várias.</p>
      </div>
      <button v-if="editable" class="btn primary" :disabled="busy" data-testid="add-purchase-request" @click="openCreate">
        <Plus :size="15" /> Adicionar
      </button>
    </div>

    <p v-if="actionError" class="notice error list-notice" role="alert">{{ actionError }}</p>

    <RequirementWaiverBanner
      v-if="requirementWaiver || (requirementGroup && requirementStage !== undefined)"
      :equipment-id="equipmentId"
      :stage="requirementStage ?? requirementWaiver!.stage"
      :group="requirementGroup"
      :waiver="requirementWaiver"
      @changed="emit('changed')"
    />

    <EquipmentPurchaseRequestsTable
      :items="sorted"
      :editable="editable"
      :busy="busy"
      @edit="openEdit"
      @delete="removeItem"
    />

    <AppModal :open="showForm" :title="editing ? 'Editar SC/OCI' : 'Nova SC/OCI'" @close="closeForm">
      <EquipmentPurchaseRequestForm
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
