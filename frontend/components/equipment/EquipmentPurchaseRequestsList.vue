<script setup lang="ts">
import { computed, reactive, ref } from "vue";
import { Pencil, Plus, Trash2 } from "lucide-vue-next";
import type { PurchaseRequest } from "~/types/equipment";
import { formatDateOnly } from "~/utils/format";
import { blankToNull } from "~/utils/workflow";

const props = defineProps<{
  equipmentId: string;
  items: PurchaseRequest[];
  editable: boolean;
}>();
const emit = defineEmits<{ changed: [] }>();

const api = useApi();
const busy = ref(false);
const actionError = ref("");
const showForm = ref(false);
const editing = ref<PurchaseRequest | null>(null);

const form = reactive({ kind: "" as "" | "SC" | "OCI", requestNumber: "", requestedAt: "" });

const sorted = computed(() => [...props.items].sort((a, b) => a.createdAt.localeCompare(b.createdAt)));

function openCreate(): void {
  editing.value = null;
  form.kind = "";
  form.requestNumber = "";
  form.requestedAt = "";
  actionError.value = "";
  showForm.value = true;
}

function openEdit(item: PurchaseRequest): void {
  editing.value = item;
  form.kind = item.kind ?? "";
  form.requestNumber = item.requestNumber ?? "";
  form.requestedAt = item.requestedAt ?? "";
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
    kind: form.kind === "" ? null : form.kind,
    requestNumber: blankToNull(form.requestNumber),
    requestedAt: blankToNull(form.requestedAt),
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

    <div v-if="sorted.length === 0" class="empty-state table-empty" data-testid="purchase-requests-empty">
      <h2>Nenhuma SC/OCI cadastrada</h2>
      <p>Adicione uma solicitação para avançar a Fase 6 (exceto sob exceção de Importação).</p>
    </div>
    <div v-else class="table-wrap">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Tipo</TableHead>
            <TableHead>Número</TableHead>
            <TableHead>Data</TableHead>
            <TableHead />
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow v-for="item in sorted" :key="item.id" :data-testid="`purchase-request-${item.id}`">
            <TableCell class="font-semibold">{{ item.kind ?? "—" }}</TableCell>
            <TableCell>{{ item.requestNumber ?? "—" }}</TableCell>
            <TableCell>{{ formatDateOnly(item.requestedAt) }}</TableCell>
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

    <AppModal :open="showForm" :title="editing ? 'Editar SC/OCI' : 'Nova SC/OCI'" @close="closeForm">
      <form class="item-form" @submit.prevent="submit">
        <label class="field">
          <span>Tipo</span>
          <select v-model="form.kind">
            <option value="">Não informado</option>
            <option value="SC">SC</option>
            <option value="OCI">OCI</option>
          </select>
        </label>
        <label class="field"><span>Número</span><input v-model="form.requestNumber" maxlength="80"></label>
        <label class="field"><span>Data</span><input v-model="form.requestedAt" type="date"></label>
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
.field input, .field select { border: 1px solid #d8dee7; border-radius: 6px; padding: 7px 9px; font-size: 13px; }
.form-actions { display: flex; justify-content: flex-end; gap: 9px; }
</style>
