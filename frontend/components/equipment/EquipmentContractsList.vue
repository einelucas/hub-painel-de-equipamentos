<script setup lang="ts">
import { computed, reactive, ref } from "vue";
import { Download, Pencil, Plus, Trash2, Upload } from "lucide-vue-next";
import type { Contract } from "~/types/equipment";
import { formatDateOnly } from "~/utils/format";
import { blankToNull } from "~/utils/workflow";

const props = defineProps<{
  equipmentId: string;
  contracts: Contract[];
  editable: boolean;
}>();
const emit = defineEmits<{ changed: [] }>();

const api = useApi();
const busy = ref(false);
const actionError = ref("");
const showForm = ref(false);
const editing = ref<Contract | null>(null);
const fileInput = ref<HTMLInputElement | null>(null);
const pendingFile = ref<File | null>(null);

const form = reactive({ contractNumber: "", executedAt: "" });

const sorted = computed(() =>
  [...props.contracts].sort((a, b) => a.createdAt.localeCompare(b.createdAt)),
);

function openCreate(): void {
  editing.value = null;
  form.contractNumber = "";
  form.executedAt = "";
  pendingFile.value = null;
  actionError.value = "";
  showForm.value = true;
}

function openEdit(item: Contract): void {
  editing.value = item;
  form.contractNumber = item.contractNumber ?? "";
  form.executedAt = item.executedAt ?? "";
  pendingFile.value = null;
  actionError.value = "";
  showForm.value = true;
}

function closeForm(): void {
  showForm.value = false;
  editing.value = null;
}

function pickFile(): void {
  fileInput.value?.click();
}

function onFileChosen(event: Event): void {
  const target = event.target as HTMLInputElement;
  pendingFile.value = target.files?.[0] ?? null;
}

async function uploadFile(contractId: string): Promise<void> {
  if (!pendingFile.value) return;
  const body = new FormData();
  body.append("file", pendingFile.value);
  await api.request(`/equipments/${props.equipmentId}/contracts/${contractId}/file`, {
    method: "PUT",
    body: body as never,
  });
}

async function submit(): Promise<void> {
  busy.value = true;
  actionError.value = "";
  const payload = {
    contractNumber: blankToNull(form.contractNumber),
    executedAt: blankToNull(form.executedAt),
  };
  try {
    if (editing.value) {
      await api.patch(`/equipments/${props.equipmentId}/contracts/${editing.value.id}`, payload);
      if (pendingFile.value) await uploadFile(editing.value.id);
    } else {
      const created = await api.post<Contract>(`/equipments/${props.equipmentId}/contracts`, payload);
      if (pendingFile.value) await uploadFile(created.id);
    }
    showForm.value = false;
    emit("changed");
  } catch (caught) {
    actionError.value = caught instanceof Error ? caught.message : "Não foi possível salvar o contrato.";
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
    actionError.value = caught instanceof Error ? caught.message : "Não foi possível excluir o contrato.";
  } finally {
    busy.value = false;
  }
}

async function downloadFile(item: Contract): Promise<void> {
  if (!item.file) return;
  const blob = await api.request<Blob>(`/equipments/${props.equipmentId}/contracts/${item.id}/file`, {
    method: "GET",
    responseType: "blob",
  });
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
        <p>Um equipamento pode ter vários contratos. Cada um tem seu próprio arquivo.</p>
      </div>
      <button v-if="editable" class="btn primary" :disabled="busy" data-testid="add-contract" @click="openCreate">
        <Plus :size="15" /> Adicionar
      </button>
    </div>

    <p v-if="actionError" class="notice error list-notice" role="alert">{{ actionError }}</p>

    <div v-if="sorted.length === 0" class="empty-state table-empty" data-testid="contracts-empty">
      <h2>Nenhum contrato cadastrado</h2>
      <p>Adicione um contrato para escriturar o processo (Fase 5).</p>
    </div>
    <div v-else class="table-wrap">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Número</TableHead>
            <TableHead>Escrituração</TableHead>
            <TableHead>Arquivo</TableHead>
            <TableHead />
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow v-for="item in sorted" :key="item.id" :data-testid="`contract-${item.id}`">
            <TableCell class="font-semibold">{{ item.contractNumber ?? "—" }}</TableCell>
            <TableCell>{{ formatDateOnly(item.executedAt) }}</TableCell>
            <TableCell>
              <button v-if="item.file" class="text-button" @click="downloadFile(item)">
                <Download :size="13" /> {{ item.file.fileName }}
              </button>
              <span v-else>—</span>
            </TableCell>
            <TableCell class="row-actions">
              <button v-if="editable" class="text-button" @click="openEdit(item)"><Pencil :size="13" /> Editar</button>
              <button v-if="editable" class="text-button danger" :disabled="busy" @click="removeContract(item)">
                <Trash2 :size="13" /> Excluir
              </button>
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </div>

    <AppModal :open="showForm" :title="editing ? 'Editar contrato' : 'Novo contrato'" @close="closeForm">
      <form class="item-form" @submit.prevent="submit">
        <label class="field"><span>Número do contrato</span><input v-model="form.contractNumber" maxlength="80"></label>
        <label class="field"><span>Data de escrituração</span><input v-model="form.executedAt" type="date"></label>
        <label class="field">
          <span>Arquivo do contrato</span>
          <button type="button" class="btn file-picker" @click="pickFile">
            <Upload :size="14" /> {{ pendingFile ? pendingFile.name : (editing?.file?.fileName ?? "Selecionar arquivo") }}
          </button>
          <input ref="fileInput" type="file" class="hidden-input" @change="onFileChosen">
        </label>
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
.file-picker { justify-content: flex-start; gap: 7px; }
.hidden-input { display: none; }
.form-actions { display: flex; justify-content: flex-end; gap: 9px; }
</style>
