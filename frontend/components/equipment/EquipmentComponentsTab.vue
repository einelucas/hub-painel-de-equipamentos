<script setup lang="ts">
import { ref } from "vue";
import { Plus } from "lucide-vue-next";
import type { EquipmentComponent } from "~/types/equipment";
import { formatDateOnly } from "~/utils/format";

/**
 * Aba "Componentes" — cabeçalho, tabela, expansão de prazos calculados por
 * linha e o modal de cadastro/edição (reaproveita `ComponentForm` como
 * está). A página continua sendo a única fonte de dados (`detail`); este
 * componente só apresenta a lista recebida e avisa quando precisa recarregar.
 */
defineProps<{
  equipmentId: string;
  components: EquipmentComponent[];
  canEdit: boolean;
}>();
/** Emitido após criar/editar um componente com sucesso — a página recarrega
 * o equipamento (mesma recarga de `loadEquipment` já existente). */
const emit = defineEmits<{ saved: [] }>();

const showComponent = ref(false);
const editingComponent = ref<EquipmentComponent | null>(null);
const expandedComponentId = ref<string | null>(null);

function toggleComponentDeadlines(componentId: string): void {
  expandedComponentId.value = expandedComponentId.value === componentId ? null : componentId;
}

function openCreate(): void {
  editingComponent.value = null;
  showComponent.value = true;
}

function editComponent(component: EquipmentComponent): void {
  editingComponent.value = component;
  showComponent.value = true;
}

function closeComponent(): void {
  showComponent.value = false;
  editingComponent.value = null;
}

async function componentSaved(_component: EquipmentComponent): Promise<void> {
  showComponent.value = false;
  editingComponent.value = null;
  emit("saved");
}
</script>

<template>
  <section class="surface">
    <div class="surface-header">
      <div>
        <h2>Componentes</h2>
        <p>{{ components.length }} subitem(ns) cadastrado(s).</p>
      </div>
      <button v-if="canEdit" class="btn primary" @click="openCreate">
        <Plus :size="15" /> Adicionar componente
      </button>
    </div>
    <div v-if="components.length === 0" class="empty-state table-empty">
      <h2>Nenhum componente cadastrado</h2>
      <p>Os componentes deste equipamento aparecerão aqui.</p>
    </div>
    <div v-else class="table-wrap">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Componente</TableHead>
            <TableHead>Tag</TableHead>
            <TableHead>Startup</TableHead>
            <TableHead>Setor</TableHead>
            <TableHead>Lead time</TableHead>
            <TableHead>Pré-start</TableHead>
            <TableHead>Entrega contratual</TableHead>
            <TableHead>Frete</TableHead>
            <TableHead />
          </TableRow>
        </TableHeader>
        <TableBody>
          <template v-for="component in components" :key="component.id">
            <TableRow>
              <TableCell class="font-semibold">{{ component.name }}</TableCell>
              <TableCell>{{ component.tag ?? "—" }}</TableCell>
              <TableCell>{{ formatDateOnly(component.startupAt) }}</TableCell>
              <TableCell>{{ component.sector ?? "—" }}</TableCell>
              <TableCell>{{ component.leadTimeDays === null ? "—" : `${component.leadTimeDays} dias` }}</TableCell>
              <TableCell>{{ component.preStartDays === null ? "—" : `${component.preStartDays} dias` }}</TableCell>
              <TableCell>{{ formatDateOnly(component.contractDeliveryAt) }}</TableCell>
              <TableCell>{{ component.freightDays === null ? "—" : `${component.freightDays} dias` }}</TableCell>
              <TableCell class="component-actions">
                <button
                  class="text-button"
                  :data-testid="`toggle-deadlines-${component.id}`"
                  @click="toggleComponentDeadlines(component.id)"
                >
                  {{ expandedComponentId === component.id ? "Ocultar prazos" : "Prazos calculados" }}
                </button>
                <button v-if="canEdit" class="text-button" @click="editComponent(component)">Editar</button>
              </TableCell>
            </TableRow>
            <TableRow v-if="expandedComponentId === component.id" class="deadlines-row">
              <TableCell colspan="9">
                <div class="deadlines-grid" :data-testid="`deadlines-${component.id}`">
                  <div class="detail-field"><span>Limite entrega em obra</span><strong>{{ formatDateOnly(component.calculated.deliveryDeadline) }}</strong></div>
                  <div class="detail-field"><span>Disponível coleta</span><strong>{{ formatDateOnly(component.calculated.availableForCollection) }}</strong></div>
                  <div class="detail-field"><span>Limite contrato/OC</span><strong>{{ formatDateOnly(component.calculated.contractOrderDeadline) }}</strong></div>
                  <div class="detail-field"><span>Limite negociação</span><strong>{{ formatDateOnly(component.calculated.negotiationDeadline) }}</strong></div>
                </div>
              </TableCell>
            </TableRow>
          </template>
        </TableBody>
      </Table>
    </div>
  </section>

  <AppModal :open="showComponent" :title="editingComponent ? 'Editar componente' : 'Novo componente'" @close="closeComponent">
    <ComponentForm
      v-if="showComponent"
      :equipment-id="equipmentId"
      :component="editingComponent"
      @saved="componentSaved"
      @cancel="closeComponent"
    />
  </AppModal>
</template>

<style scoped>
.detail-field { display: grid; align-content: start; gap: 5px; }
.detail-field > span { color: #7a879a; font-size: 10px; font-weight: 800; letter-spacing: .05em; text-transform: uppercase; }
.detail-field strong { color: #2b3e58; font-size: 13px; font-weight: 700; }
.table-wrap { padding: 0 18px 18px; }
.table-empty { margin: auto; }
.component-actions { display: flex; gap: 12px; white-space: nowrap; }
.deadlines-row { background: #fafbfc; }
.deadlines-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px 18px; padding: 6px 4px; }
@media (max-width: 900px) { .deadlines-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
.text-button { border: 0; padding: 4px; background: transparent; color: #304f7e; font-size: 12px; font-weight: 750; }
.text-button.danger { color: #a4453a; }
</style>
