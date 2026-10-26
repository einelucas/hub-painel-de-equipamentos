<script setup lang="ts">
import { computed } from "vue";
import { Info, Layers, Package, Pencil, Plus, Power, Trash2 } from "lucide-vue-next";
import Badge from "~/components/ui/Badge.vue";
import Button from "~/components/ui/Button.vue";
import Checkbox from "~/components/ui/Checkbox.vue";
import Input from "~/components/ui/Input.vue";
import LoadingSpinner from "~/components/ui/LoadingSpinner.vue";
import Table from "~/components/ui/Table.vue";
import TableBody from "~/components/ui/TableBody.vue";
import TableCell from "~/components/ui/TableCell.vue";
import TableHead from "~/components/ui/TableHead.vue";
import TableHeader from "~/components/ui/TableHeader.vue";
import TableRow from "~/components/ui/TableRow.vue";
import type { MasterArea, MasterComponent, MasterEquipment } from "~/types/masterCatalog";
import {
  activeRealAreas,
  buildAreaMap,
  componentCountLabel,
  findUnassignedArea,
  fullAreaSummary,
  inactiveLinkedAreas,
} from "~/utils/masterCatalog";

const props = defineProps<{
  equipment: MasterEquipment | null;
  areas: MasterArea[];
  draftAreas: string[];
  areasDirty: boolean;
  loading: boolean;
  busy: boolean;
  savingAreas: boolean;
  deletingId: string;
  componentError: string;
}>();

const newComponentName = defineModel<string>("newComponentName", { required: true });

const emit = defineEmits<{
  renameEquipment: [];
  toggleEquipment: [];
  removeEquipment: [];
  toggleArea: [areaId: string];
  saveAreas: [];
  discardAreas: [];
  addComponent: [name: string];
  renameComponent: [component: MasterComponent];
  toggleComponent: [component: MasterComponent];
  removeComponent: [component: MasterComponent];
}>();

const areaMap = computed(() => buildAreaMap(props.areas));
const realAreas = computed(() => activeRealAreas(props.areas));
const unassignedArea = computed(() => findUnassignedArea(props.areas));
const selectedAreaCount = computed(
  () => props.draftAreas.filter((id) => areaMap.value.get(id)?.active).length,
);
const inactiveAreas = computed(() =>
  props.equipment ? inactiveLinkedAreas(props.equipment, areaMap.value) : [],
);
const equipmentDeleting = computed(
  () => Boolean(props.equipment) && props.deletingId === `/master-catalog/equipments/${props.equipment?.id}`,
);

function submitComponent(): void {
  const name = newComponentName.value.trim();
  if (!name || props.busy) return;
  emit("addComponent", name);
}

function isComponentDeleting(component: MasterComponent): boolean {
  return props.deletingId === `/master-catalog/components/${component.id}`;
}
</script>

<template>
  <section class="master-detail" aria-label="Detalhes do equipamento">
    <div v-if="props.loading && !props.equipment" class="surface detail-state">
      <LoadingSpinner label="Carregando catálogo..." />
    </div>

    <div v-else-if="!props.equipment" class="surface detail-state detail-state--empty">
      <span class="detail-state__icon"><Package :size="26" aria-hidden="true" /></span>
      <h2>Comece seu catálogo</h2>
      <p>
        Crie o primeiro equipamento mestre ou importe um seed para montar a base usada
        em novas obras.
      </p>
    </div>

    <article v-else class="surface detail-card" :aria-busy="props.loading || props.busy">
      <header class="detail-head">
        <div class="detail-identity">
          <p class="eyebrow">Equipamento mestre</p>
          <div class="detail-title-row">
            <h2>{{ props.equipment.name }}</h2>
            <Badge :variant="props.equipment.active ? 'success' : 'secondary'">
              {{ props.equipment.active ? "Ativo" : "Inativo" }}
            </Badge>
          </div>
          <p class="detail-meta">
            <Layers :size="14" aria-hidden="true" />
            {{ fullAreaSummary(props.equipment, areaMap) }}
            <span aria-hidden="true">·</span>
            {{ componentCountLabel(props.equipment.components.length) }}
          </p>
        </div>

        <div class="detail-actions">
          <Button variant="outline" size="sm" :disabled="props.busy" @click="emit('renameEquipment')">
            <Pencil aria-hidden="true" /> Renomear
          </Button>
          <Button variant="outline" size="sm" :disabled="props.busy" @click="emit('toggleEquipment')">
            <Power aria-hidden="true" />
            {{ props.equipment.active ? "Desativar" : "Reativar" }}
          </Button>
          <Button
            variant="destructive"
            size="sm"
            :disabled="props.busy"
            :loading="equipmentDeleting"
            @click="emit('removeEquipment')"
          >
            <Trash2 v-if="!equipmentDeleting" aria-hidden="true" /> Excluir
          </Button>
        </div>
      </header>

      <div class="detail-grid">
        <section class="detail-section areas-section">
          <header class="section-heading">
            <div>
              <h3>Áreas</h3>
              <p>Onde este modelo pode ser usado nas novas obras.</p>
            </div>
            <Badge variant="secondary">
              {{ selectedAreaCount }} selecionada{{ selectedAreaCount === 1 ? "" : "s" }}
            </Badge>
          </header>

          <p v-if="inactiveAreas.length" class="inline-warning">
            <Info :size="14" aria-hidden="true" />
            {{
              inactiveAreas.length === 1
                ? "Há uma área inativa vinculada"
                : `Há ${inactiveAreas.length} áreas inativas vinculadas`
            }}. O vínculo será removido ao salvar as áreas.
          </p>

          <fieldset class="area-options" :disabled="props.busy">
            <legend class="sr-only">Áreas do equipamento</legend>
            <label
              v-if="unassignedArea"
              class="area-option area-option--virtual"
              :class="{ selected: props.draftAreas.includes(unassignedArea.id) }"
            >
              <Checkbox
                :model-value="props.draftAreas.includes(unassignedArea.id)"
                @update:model-value="emit('toggleArea', unassignedArea.id)"
              />
              <span>
                <strong>Sem área definida</strong>
                <small>Para modelos ainda não classificados</small>
              </span>
            </label>
            <label
              v-for="area in realAreas"
              :key="area.id"
              class="area-option"
              :class="{ selected: props.draftAreas.includes(area.id) }"
            >
              <Checkbox
                :model-value="props.draftAreas.includes(area.id)"
                @update:model-value="emit('toggleArea', area.id)"
              />
              <span>{{ area.name }}</span>
            </label>
            <p v-if="!realAreas.length && !unassignedArea" class="section-empty">
              Nenhuma área ativa. Cadastre áreas em “Gerenciar áreas”.
            </p>
          </fieldset>

          <div v-if="props.areasDirty" class="unsaved-bar">
            <span class="unsaved-label">
              <span class="unsaved-dot" aria-hidden="true" /> Alterações não salvas
            </span>
            <div class="unsaved-actions">
              <Button
                variant="ghost"
                size="sm"
                :disabled="props.busy"
                @click="emit('discardAreas')"
              >
                Descartar
              </Button>
              <Button
                size="sm"
                :disabled="props.busy"
                :loading="props.savingAreas"
                @click="emit('saveAreas')"
              >
                {{ props.savingAreas ? "Salvando..." : "Salvar áreas" }}
              </Button>
            </div>
          </div>

          <p class="section-note">A classificação mestre não altera a EAP de nenhuma obra.</p>
        </section>

        <section class="detail-section components-section">
          <header class="section-heading">
            <div>
              <h3>Componentes opcionais</h3>
              <p>Itens que podem ser adicionados ao equipamento em novas obras.</p>
            </div>
            <Badge variant="secondary">{{ props.equipment.components.length }}</Badge>
          </header>

          <form class="quick-add" @submit.prevent="submitComponent">
            <Input
              v-model="newComponentName"
              maxlength="500"
              placeholder="Nome do novo componente"
              aria-label="Nome do novo componente"
              :disabled="props.busy"
            />
            <Button
              type="submit"
              size="sm"
              :disabled="props.busy || !newComponentName.trim()"
            >
              <Plus aria-hidden="true" /> Adicionar
            </Button>
          </form>
          <p v-if="props.componentError" class="inline-error" role="alert">
            {{ props.componentError }}
          </p>

          <div class="components-table">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Componente</TableHead>
                  <TableHead>Situação</TableHead>
                  <TableHead class="actions-heading">Ações</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                <TableRow v-if="!props.equipment.components.length">
                  <TableCell colspan="3">
                    <p class="table-empty">
                      Nenhum componente cadastrado. Adicione o primeiro acima.
                    </p>
                  </TableCell>
                </TableRow>
                <TableRow v-for="component in props.equipment.components" :key="component.id">
                  <TableCell class="component-name">{{ component.name }}</TableCell>
                  <TableCell>
                    <Badge :variant="component.active ? 'success' : 'secondary'">
                      {{ component.active ? "Ativo" : "Inativo" }}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <div class="row-actions">
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        :disabled="props.busy"
                        :aria-label="`Renomear ${component.name}`"
                        :title="`Renomear ${component.name}`"
                        @click="emit('renameComponent', component)"
                      >
                        <Pencil aria-hidden="true" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        :disabled="props.busy"
                        :aria-label="`${component.active ? 'Desativar' : 'Reativar'} ${component.name}`"
                        :title="`${component.active ? 'Desativar' : 'Reativar'} ${component.name}`"
                        @click="emit('toggleComponent', component)"
                      >
                        <Power aria-hidden="true" />
                      </Button>
                      <Button
                        variant="destructive"
                        size="icon-sm"
                        :disabled="props.busy"
                        :loading="isComponentDeleting(component)"
                        :aria-label="`Excluir ${component.name}`"
                        :title="`Excluir ${component.name}`"
                        @click="emit('removeComponent', component)"
                      >
                        <Trash2 v-if="!isComponentDeleting(component)" aria-hidden="true" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </div>

          <p class="section-note">
            Componentes inativos permanecem no histórico das obras e deixam de aparecer
            em novos cadastros.
          </p>
        </section>
      </div>
    </article>
  </section>
</template>

<style scoped>
.master-detail {
  min-width: 0;
}

.detail-state {
  display: grid;
  min-height: 430px;
  place-items: center;
  align-content: center;
  gap: 10px;
  padding: 32px;
  text-align: center;
}

.detail-state--empty h2 {
  margin: 2px 0 0;
  color: #243a57;
  font-size: 20px;
  font-weight: 800;
}

.detail-state p {
  max-width: 390px;
  margin: 0;
  color: #7d8a9c;
  font-size: 13px;
  line-height: 1.55;
}

.detail-state__icon {
  display: grid;
  width: 56px;
  height: 56px;
  place-items: center;
  border-radius: 16px;
  background: #eef4fb;
  color: #557aa8;
}

.detail-card {
  overflow: hidden;
}

.detail-head {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  border-bottom: 1px solid #edf1f5;
  padding: 21px 22px 18px;
  background: linear-gradient(180deg, #fff 0%, #fcfdff 100%);
}

.detail-identity {
  min-width: 0;
}

.eyebrow {
  margin: 0 0 6px;
  color: #2e5aac;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.detail-title-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 9px;
}

.detail-title-row h2 {
  max-width: 100%;
  margin: 0;
  overflow-wrap: anywhere;
  color: #20324a;
  font-size: clamp(20px, 2vw, 25px);
  font-weight: 800;
  letter-spacing: -0.015em;
  line-height: 1.15;
}

.detail-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin: 8px 0 0;
  color: #708096;
  font-size: 12px;
}

.detail-meta svg {
  color: #6f8db3;
}

.detail-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 7px;
}

.detail-grid {
  display: grid;
  grid-template-columns: minmax(280px, 0.9fr) minmax(360px, 1.1fr);
}

.detail-section {
  min-width: 0;
  padding: 20px 22px;
}

.areas-section {
  border-right: 1px solid #edf1f5;
  background: #fcfdff;
}

.section-heading {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 13px;
}

.section-heading h3 {
  margin: 0;
  color: #243a57;
  font-size: 15px;
  font-weight: 800;
}

.section-heading p {
  max-width: 380px;
  margin: 3px 0 0;
  color: #7d8a9c;
  font-size: 11.5px;
  line-height: 1.5;
}

.area-options {
  display: grid;
  min-width: 0;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  max-height: 330px;
  gap: 7px;
  margin: 0;
  border: 0;
  padding: 0 3px 0 0;
  overflow-y: auto;
  overscroll-behavior: contain;
}

.area-option {
  display: flex;
  min-width: 0;
  align-items: flex-start;
  gap: 9px;
  border: 1px solid #e1e8f1;
  border-radius: 9px;
  padding: 9px 10px;
  background: #fff;
  color: #354a64;
  font-size: 12px;
  line-height: 1.4;
  cursor: pointer;
  transition:
    border-color 0.15s ease,
    background 0.15s ease;
}

.area-option:hover {
  border-color: #c9d8ea;
}

.area-options:disabled .area-option {
  cursor: default;
  opacity: 0.7;
}

.area-options:disabled .area-option:hover {
  border-color: #e1e8f1;
}

.area-option.selected {
  border-color: #a9c5e6;
  background: #f1f7fe;
}

.area-option > span {
  min-width: 0;
}

.area-option--virtual {
  grid-column: 1 / -1;
  background: #fafbfd;
}

.area-option--virtual strong,
.area-option--virtual small {
  display: block;
}

.area-option--virtual strong {
  color: #354a64;
  font-size: 12px;
}

.area-option--virtual small {
  margin-top: 1px;
  color: #8794a5;
  font-size: 10.5px;
}

.inline-warning {
  display: flex;
  align-items: flex-start;
  gap: 7px;
  margin: 0 0 10px;
  border-radius: 8px;
  padding: 8px 9px;
  background: #fff8e8;
  color: #7c5c1f;
  font-size: 11px;
  line-height: 1.45;
}

.inline-warning svg {
  flex: 0 0 auto;
  margin-top: 1px;
}

.inline-error {
  margin: 9px 0 0;
  color: #a4453a;
  font-size: 11.5px;
  font-weight: 700;
  line-height: 1.45;
}

.unsaved-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-top: 11px;
  border: 1px solid #f0d28e;
  border-radius: 9px;
  padding: 8px 10px;
  background: #fff9eb;
}

.unsaved-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #7a5a1c;
  font-size: 11px;
  font-weight: 700;
}

.unsaved-dot {
  width: 7px;
  height: 7px;
  border-radius: 999px;
  background: #d99b2b;
}

.unsaved-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.quick-add {
  display: flex;
  align-items: center;
  gap: 8px;
}

.quick-add > :first-child {
  min-width: 0;
  flex: 1;
}

.quick-add :deep(input) {
  font-size: 12.5px;
}

.components-table {
  margin-top: 12px;
}

.actions-heading {
  text-align: right;
}

.component-name {
  overflow-wrap: anywhere;
  color: #354a64;
  font-size: 12px;
  font-weight: 650;
}

.row-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 3px;
}

.table-empty {
  margin: 0;
  padding: 15px 4px;
  color: #8a96a7;
  font-size: 11.5px;
  line-height: 1.5;
  text-align: center;
}

.section-note {
  margin: 11px 0 0;
  color: #8a96a7;
  font-size: 10.5px;
  line-height: 1.5;
}

.section-empty {
  margin: 0;
  color: #8a96a7;
  font-size: 11.5px;
  line-height: 1.5;
}

@media (max-width: 1180px) {
  .detail-grid {
    grid-template-columns: 1fr;
  }

  .areas-section {
    border-right: 0;
    border-bottom: 1px solid #edf1f5;
  }

  .area-options {
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    max-height: none;
  }
}

@media (max-width: 820px) {
  .detail-actions {
    width: 100%;
    justify-content: flex-start;
  }
}

@media (max-width: 560px) {
  .detail-head,
  .detail-section {
    padding: 16px;
  }

  .quick-add {
    align-items: stretch;
    flex-direction: column;
  }

  .quick-add > :last-child {
    width: 100%;
  }
}
</style>
