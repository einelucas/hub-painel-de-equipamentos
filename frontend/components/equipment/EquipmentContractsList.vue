<script setup lang="ts">
import { computed, ref } from "vue";
import { Plus } from "lucide-vue-next";
import type {
  Contract,
  RequirementGroup,
  RequirementWaiver,
} from "~/types/equipment";
import { blankToNull } from "~/utils/workflow";
import EquipmentContractsTable from "~/components/equipment/contracts/EquipmentContractsTable.vue";
import EquipmentContractForm, {
  type EquipmentContractFormValues,
} from "~/components/equipment/contracts/EquipmentContractForm.vue";

const props = defineProps<{
  equipmentId: string;
  contracts: Contract[];
  editable: boolean;
  /** Etapa 7.1: grupo CONTRACT da fase atual, quando ela exigir isso para
   * avançar — permite marcar "Não possui contrato" direto aqui. */
  requirementGroup?: RequirementGroup | null;
  requirementStage?: number;
  /** Dispensa ACTIVE do grupo CONTRACT, independente da fase atual — para
   * continuar visível depois que o processo avança de fase. */
  requirementWaiver?: RequirementWaiver | null;
}>();
const emit = defineEmits<{ changed: [] }>();

const api = useApi();
const busy = ref(false);
const actionError = ref("");
const showForm = ref(false);
const editing = ref<Contract | null>(null);

const sorted = computed(() =>
  [...props.contracts].sort((a, b) => a.createdAt.localeCompare(b.createdAt)),
);

function openCreate(): void {
  editing.value = null;
  actionError.value = "";
  showForm.value = true;
}

function openEdit(item: Contract): void {
  editing.value = item;
  actionError.value = "";
  showForm.value = true;
}

function closeForm(): void {
  showForm.value = false;
  editing.value = null;
}

async function uploadFile(contractId: string, file: File): Promise<void> {
  const body = new FormData();
  body.append("file", file);
  await api.request(
    `/equipments/${props.equipmentId}/contracts/${contractId}/file`,
    {
      method: "PUT",
      body: body as never,
    },
  );
}

async function submit(values: EquipmentContractFormValues): Promise<void> {
  busy.value = true;
  actionError.value = "";
  const payload = {
    contractNumber: blankToNull(values.contractNumber),
    executedAt: blankToNull(values.executedAt),
  };
  try {
    if (editing.value) {
      await api.patch(
        `/equipments/${props.equipmentId}/contracts/${editing.value.id}`,
        payload,
      );
      if (values.file) await uploadFile(editing.value.id, values.file);
    } else {
      const created = await api.post<Contract>(
        `/equipments/${props.equipmentId}/contracts`,
        payload,
      );
      if (values.file) await uploadFile(created.id, values.file);
    }
    showForm.value = false;
    emit("changed");
  } catch (caught) {
    actionError.value =
      caught instanceof Error
        ? caught.message
        : "Não foi possível salvar o contrato.";
  } finally {
    busy.value = false;
  }
}

async function removeContract(item: Contract): Promise<void> {
  busy.value = true;
  actionError.value = "";
  try {
    await api.delete(`/equipments/${props.equipmentId}/contracts/${item.id}`);
    emit("changed");
  } catch (caught) {
    actionError.value =
      caught instanceof Error
        ? caught.message
        : "Não foi possível excluir o contrato.";
  } finally {
    busy.value = false;
  }
}

async function downloadFile(item: Contract): Promise<void> {
  if (!item.file) return;
  const blob = await api.request<Blob>(
    `/equipments/${props.equipmentId}/contracts/${item.id}/file`,
    {
      method: "GET",
      responseType: "blob",
    },
  );
  const url = URL.createObjectURL(blob as Blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = item.file.fileName;
  link.click();
  URL.revokeObjectURL(url);
}
</script>

<template>
  <section class="surface">
    <div class="surface-header">
      <div>
        <h2>Contratos</h2>
        <p>
          Um equipamento pode ter vários contratos. Cada um tem seu próprio
          arquivo.
        </p>
      </div>
      <button
        v-if="editable"
        class="btn primary"
        :disabled="busy"
        data-testid="add-contract"
        @click="openCreate"
      >
        <Plus :size="15" /> Adicionar
      </button>
    </div>

    <p v-if="actionError" class="notice error list-notice" role="alert">
      {{ actionError }}
    </p>

    <RequirementWaiverBanner
      v-if="
        requirementWaiver ||
        (requirementGroup && requirementStage !== undefined)
      "
      :equipment-id="equipmentId"
      :stage="requirementStage ?? requirementWaiver!.stage"
      :group="requirementGroup"
      :waiver="requirementWaiver"
      @changed="emit('changed')"
    />

    <EquipmentContractsTable
      :contracts="sorted"
      :editable="editable"
      :busy="busy"
      @edit="openEdit"
      @delete="removeContract"
      @download="downloadFile"
    />

    <AppModal
      :open="showForm"
      :title="editing ? 'Editar contrato' : 'Novo contrato'"
      @close="closeForm"
    >
      <EquipmentContractForm
        :contract="editing"
        :busy="busy"
        :error="actionError"
        @submit="submit"
        @cancel="closeForm"
      />
    </AppModal>
  </section>
</template>

<style scoped>
.list-notice {
  margin: 0 18px 14px;
}
</style>
