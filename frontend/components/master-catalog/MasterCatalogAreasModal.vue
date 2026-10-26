<script setup lang="ts">
import { computed } from "vue";
import { Pencil, Plus, Power, Trash2 } from "lucide-vue-next";
import AppModal from "~/components/ui/AppModal.vue";
import Badge from "~/components/ui/Badge.vue";
import Button from "~/components/ui/Button.vue";
import Input from "~/components/ui/Input.vue";
import Table from "~/components/ui/Table.vue";
import TableBody from "~/components/ui/TableBody.vue";
import TableCell from "~/components/ui/TableCell.vue";
import TableHead from "~/components/ui/TableHead.vue";
import TableHeader from "~/components/ui/TableHeader.vue";
import TableRow from "~/components/ui/TableRow.vue";
import type { MasterArea, MasterEquipment } from "~/types/masterCatalog";
import { areaUsage } from "~/utils/masterCatalog";

const props = defineProps<{
  open: boolean;
  areas: MasterArea[];
  equipments: MasterEquipment[];
  busy: boolean;
  deletingId: string;
  error: string;
}>();

const newAreaName = defineModel<string>("newAreaName", { required: true });

const emit = defineEmits<{
  close: [];
  add: [name: string];
  rename: [area: MasterArea];
  toggle: [area: MasterArea];
  remove: [area: MasterArea];
}>();

const managedAreas = computed(() =>
  [...props.areas].sort((left, right) => {
    if (left.isUnassigned !== right.isUnassigned) return left.isUnassigned ? -1 : 1;
    if (left.active !== right.active) return left.active ? -1 : 1;
    return left.name.localeCompare(right.name, "pt-BR");
  }),
);

function isDeleting(area: MasterArea): boolean {
  return props.deletingId === `/master-catalog/areas/${area.id}`;
}

function addArea(): void {
  const name = newAreaName.value.trim();
  if (!name || props.busy) return;
  emit("add", name);
}
</script>

<template>
  <AppModal
    :open="props.open"
    title="Áreas do catálogo"
    :busy="props.busy"
    @close="emit('close')"
  >
    <div class="areas-modal">
      <p class="modal-intro">
        As áreas classificam os equipamentos e ficam disponíveis na criação de novas
        obras. Áreas inativas continuam visíveis aqui, mas não podem ser associadas.
      </p>

      <form class="add-area" @submit.prevent="addArea">
        <Input
          v-model="newAreaName"
          maxlength="160"
          placeholder="Nome da nova área"
          aria-label="Nome da nova área"
          :disabled="props.busy"
        />
        <Button type="submit" size="sm" :disabled="props.busy || !newAreaName.trim()">
          <Plus aria-hidden="true" /> Adicionar
        </Button>
      </form>

      <p v-if="props.error" class="notice error" role="alert">{{ props.error }}</p>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Área</TableHead>
            <TableHead>Uso</TableHead>
            <TableHead>Situação</TableHead>
            <TableHead class="actions-heading">Ações</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow v-for="area in managedAreas" :key="area.id">
            <TableCell>
              <div class="area-name">
                <strong>{{ area.name }}</strong>
                <Badge v-if="area.isUnassigned" variant="outline">Padrão do sistema</Badge>
              </div>
            </TableCell>
            <TableCell class="area-usage">{{ areaUsage(area, props.equipments) }}</TableCell>
            <TableCell>
              <Badge :variant="area.active ? 'success' : 'secondary'">
                {{ area.active ? "Ativa" : "Inativa" }}
              </Badge>
            </TableCell>
            <TableCell>
              <div v-if="!area.isUnassigned" class="row-actions">
                <Button
                  variant="ghost"
                  size="icon-sm"
                  :disabled="props.busy"
                  :aria-label="`Renomear ${area.name}`"
                  :title="`Renomear ${area.name}`"
                  @click="emit('rename', area)"
                >
                  <Pencil aria-hidden="true" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon-sm"
                  :disabled="props.busy"
                  :aria-label="`${area.active ? 'Desativar' : 'Reativar'} ${area.name}`"
                  :title="`${area.active ? 'Desativar' : 'Reativar'} ${area.name}`"
                  @click="emit('toggle', area)"
                >
                  <Power aria-hidden="true" />
                </Button>
                <Button
                  variant="destructive"
                  size="icon-sm"
                  :disabled="props.busy"
                  :loading="isDeleting(area)"
                  :aria-label="`Excluir ${area.name}`"
                  :title="`Excluir ${area.name}`"
                  @click="emit('remove', area)"
                >
                  <Trash2 v-if="!isDeleting(area)" aria-hidden="true" />
                </Button>
              </div>
              <Badge v-else variant="secondary">Protegida</Badge>
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>

      <p class="modal-note">
        A categoria “Sem área definida” é protegida pelo sistema. Excluir uma área
        remove o vínculo dos equipamentos mestres, sem alterar obras já criadas.
      </p>
    </div>

    <template #actions>
      <Button variant="outline" size="sm" :disabled="props.busy" @click="emit('close')">
        Fechar
      </Button>
    </template>
  </AppModal>
</template>

<style scoped>
.areas-modal {
  display: grid;
  gap: 14px;
}

.modal-intro,
.modal-note {
  margin: 0;
  color: #64748b;
  font-size: 12px;
  line-height: 1.55;
}

.modal-note {
  color: #8a96a7;
  font-size: 10.5px;
}

.add-area {
  display: flex;
  align-items: center;
  gap: 8px;
}

.add-area > :first-child {
  min-width: 0;
  flex: 1;
}

.add-area :deep(input) {
  font-size: 12.5px;
}

.area-name {
  display: flex;
  min-width: 0;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.area-name strong {
  overflow-wrap: anywhere;
  color: #354a64;
  font-size: 12px;
}

.area-usage {
  max-width: 220px;
  color: #7b8798;
  font-size: 10.5px;
  line-height: 1.4;
}

.actions-heading {
  text-align: right;
}

.row-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 3px;
}

@media (max-width: 560px) {
  .add-area {
    align-items: stretch;
    flex-direction: column;
  }

  .add-area > :last-child {
    width: 100%;
  }
}
</style>
