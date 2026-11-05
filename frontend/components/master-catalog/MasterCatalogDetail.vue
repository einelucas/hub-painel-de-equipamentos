<script setup lang="ts">
import {
  mdiCheck,
  mdiChevronDown,
  mdiDotsVertical,
  mdiPencilOutline,
  mdiPlus,
  mdiPower,
  mdiTrashCanOutline,
} from "@mdi/js";
import { computed } from "vue";
import { Boxes, CircleHelp, Info, Layers3, Package, SearchX } from "lucide-vue-next";
import {
  VAutocomplete, VBtn, VChip, VIcon, VList, VListItem, VMenu, VTextField,
} from "vuetify/components";
import Badge from "~/components/ui/Badge.vue";
import LoadingSpinner from "~/components/ui/LoadingSpinner.vue";
import type { MasterArea, MasterComponent, MasterEquipment } from "~/types/masterCatalog";
import {
  activeRealAreas, buildAreaMap, findUnassignedArea, inactiveLinkedAreas,
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
const linkedAreas = computed(() => realAreas.value.filter((area) => props.draftAreas.includes(area.id)));
const availableAreas = computed(() =>
  realAreas.value
    .filter((area) => !props.draftAreas.includes(area.id))
    .map((area) => ({ title: area.name, value: area.id })),
);
const inactiveAreas = computed(() =>
  props.equipment ? inactiveLinkedAreas(props.equipment, areaMap.value) : [],
);
const selectedVirtual = computed(() => {
  const area = unassignedArea.value;
  return area ? props.draftAreas.includes(area.id) : false;
});
const activeComponents = computed(() =>
  props.equipment?.components.filter((component) => component.active).length ?? 0,
);
const sortedComponents = computed(() => [...(props.equipment?.components ?? [])].sort((a, b) =>
  Number(b.active) - Number(a.active) || a.name.localeCompare(b.name, "pt-BR"),
));
const equipmentDeleting = computed(() =>
  Boolean(props.equipment) &&
  props.deletingId === `/master-catalog/equipments/${props.equipment?.id}`,
);

function chooseArea(value: unknown): void {
  if (props.busy || typeof value !== "string" || !value) return;
  if (!props.draftAreas.includes(value)) emit("toggleArea", value);
}
function removeLinkedArea(id: string): void {
  if (props.busy || !props.draftAreas.includes(id)) return;
  emit("toggleArea", id);
}
function setUnassigned(): void {
  if (props.busy || !unassignedArea.value) return;
  if (!selectedVirtual.value) emit("toggleArea", unassignedArea.value.id);
}
function submitComponent(): void {
  const name = newComponentName.value.trim();
  if (!name || props.busy) return;
  emit("addComponent", name);
}
function isComponentDeleting(item: MasterComponent): boolean {
  return props.deletingId === `/master-catalog/components/${item.id}`;
}
</script>

<template>
  <section class="master-detail" aria-label="Configuração de equipamento mestre">
    <div v-if="props.loading && !props.equipment" class="surface detail-state" role="status">
      <LoadingSpinner label="Carregando equipamento..." />
    </div>
    <div v-else-if="!props.equipment" class="surface detail-state">
      <div class="state-icon"><Package :size="27" aria-hidden="true" /></div>
      <h2>Escolha ou crie um equipamento</h2>
      <p>Selecione um modelo à esquerda para vincular áreas e cadastrar seus componentes opcionais.</p>
    </div>

    <article v-else class="surface detail-card" :aria-busy="props.busy || props.loading">
      <header class="detail-header">
        <div class="detail-header__identity">
          <p class="eyebrow">Modelo do catálogo mestre</p>
          <div class="detail-header__title">
            <h2>{{ props.equipment.name }}</h2>
            <Badge :variant="props.equipment.active ? 'success' : 'secondary'">
              {{ props.equipment.active ? 'Ativo' : 'Inativo' }}
            </Badge>
          </div>
          <p class="equipment-summary">
            {{ linkedAreas.length }} {{ linkedAreas.length === 1 ? 'área vinculada' : 'áreas vinculadas' }}
            <span aria-hidden="true">·</span>
            {{ props.equipment.components.length }} {{ props.equipment.components.length === 1 ? 'componente' : 'componentes' }}
          </p>
        </div>
        <div class="header-actions">
          <VBtn
            size="small"
            variant="outlined"
            color="secondary"
            :prepend-icon="mdiPencilOutline"
            :disabled="props.busy"
            @click="emit('renameEquipment')"
          >Renomear</VBtn>
          <VMenu>
            <template #activator="{ props: menuProps }">
              <VBtn v-bind="menuProps" size="small" variant="outlined" :append-icon="mdiChevronDown" :disabled="props.busy">
                Mais ações
              </VBtn>
            </template>
            <VList density="compact" min-width="205" class="action-menu">
              <VListItem
                :prepend-icon="mdiPower"
                :title="props.equipment.active ? 'Desativar modelo' : 'Reativar modelo'"
                @click="emit('toggleEquipment')"
              />
              <VListItem
                :prepend-icon="mdiTrashCanOutline"
                title="Excluir modelo"
                class="delete-menu-item"
                :disabled="equipmentDeleting"
                @click="emit('removeEquipment')"
              />
            </VList>
          </VMenu>
        </div>
      </header>

      <div class="relationship-note">
        <div class="relationship-note__icon"><CircleHelp :size="19" aria-hidden="true" /></div>
        <div>
          <h3>Como funcionam os vínculos?</h3>
          <p>
            Um <strong>equipamento pode ser usado em várias áreas</strong> e uma
            <strong>área pode conter vários equipamentos</strong>. Vincule as áreas abaixo
            para definir onde este modelo estará disponível ao criar novas obras.
          </p>
          <span>O catálogo é reutilizável: mudar estes vínculos não altera as obras existentes.</span>
        </div>
      </div>

      <section class="config-section" aria-labelledby="master-areas-heading">
        <div class="section-heading">
          <div class="step-marker" aria-hidden="true">2</div>
          <div class="section-heading__copy">
            <h3 id="master-areas-heading">Vincular às áreas</h3>
            <p>Escolha uma ou mais áreas onde este equipamento poderá ser utilizado.</p>
          </div>
          <Badge variant="secondary">{{ linkedAreas.length }} {{ linkedAreas.length === 1 ? 'área' : 'áreas' }}</Badge>
        </div>

        <div class="area-editor">
          <div class="area-editor__label">
            <span>Áreas vinculadas</span>
            <span class="area-editor__hint">{{ linkedAreas.length ? 'Clique no × de uma área para removê-la' : 'Nenhuma área real vinculada' }}</span>
          </div>
          <div class="selected-area-list" aria-live="polite">
            <VChip
              v-for="area in linkedAreas"
              :key="area.id"
              class="selected-area"
              variant="tonal"
              color="primary"
              size="default"
              closable
              :disabled="props.busy"
              :aria-label="`Remover vínculo com ${area.name}`"
              @click:close="removeLinkedArea(area.id)"
            >{{ area.name }}</VChip>
            <div v-if="!linkedAreas.length" class="unassigned-state">
              <SearchX :size="18" aria-hidden="true" />
              <span>{{ selectedVirtual ? 'Sem área definida (categoria do sistema)' : 'Modelo sem áreas vinculadas' }}</span>
            </div>
          </div>
          <div class="area-picker">
            <VAutocomplete
              :key="props.equipment.id"
              :model-value="null"
              :items="availableAreas"
              item-title="title"
              item-value="value"
              label="Adicionar área"
              placeholder="Pesquisar por nome e selecionar..."
              :prepend-inner-icon="mdiPlus"
              :disabled="props.busy || !availableAreas.length"
              clearable
              no-data-text="Nenhuma área disponível"
              @update:model-value="chooseArea"
            />
            <VBtn
              v-if="unassignedArea && linkedAreas.length"
              size="small"
              variant="text"
              color="secondary"
              :disabled="props.busy"
              @click="setUnassigned"
            >Deixar sem área</VBtn>
          </div>
          <p v-if="!realAreas.length" class="field-help">Não há áreas ativas. Cadastre-as em “Gerenciar áreas”.</p>
          <p v-else class="field-help">A mesma área pode ser selecionada também em outros equipamentos.</p>
        </div>

        <p v-if="inactiveAreas.length" class="warning-note" role="status">
          <Info :size="16" aria-hidden="true" />
          {{ inactiveAreas.length === 1 ? 'Uma área inativa está vinculada.' : `${inactiveAreas.length} áreas inativas estão vinculadas.` }}
          Esses vínculos serão removidos quando você salvar.
        </p>
        <div v-if="props.areasDirty" class="save-strip" role="status" aria-live="polite">
          <div class="save-strip__copy"><span class="change-dot" /> <strong>Alterações não salvas</strong><small>Confirme para atualizar os vínculos deste modelo.</small></div>
          <div class="save-strip__actions">
            <VBtn size="small" variant="text" :disabled="props.busy" @click="emit('discardAreas')">Descartar</VBtn>
            <VBtn
              size="small"
              color="primary"
              variant="flat"
              :loading="props.savingAreas"
              :disabled="props.busy"
              :prepend-icon="!props.savingAreas ? mdiCheck : undefined"
              @click="emit('saveAreas')"
            >Salvar vínculos</VBtn>
          </div>
        </div>
      </section>

      <section class="config-section config-section--components" aria-labelledby="master-components-heading">
        <div class="section-heading">
          <div class="step-marker" aria-hidden="true">3</div>
          <div class="section-heading__copy">
            <h3 id="master-components-heading">Componentes opcionais</h3>
            <p>Defina os itens que poderão ser incluídos neste modelo em novas obras.</p>
          </div>
          <Badge variant="secondary">{{ activeComponents }} {{ activeComponents === 1 ? 'ativo' : 'ativos' }}</Badge>
        </div>
        <form class="component-form" @submit.prevent="submitComponent">
          <VTextField
            v-model="newComponentName"
            label="Adicionar componente"
            placeholder="Ex.: Válvula, motor, base metálica..."
            maxlength="500"
            :disabled="props.busy"
            autocomplete="off"
            :error-messages="props.componentError ? [props.componentError] : []"
          />
          <VBtn
            type="submit"
            color="primary"
            variant="flat"
            :prepend-icon="mdiPlus"
            :disabled="props.busy || !newComponentName.trim()"
          >Adicionar</VBtn>
        </form>
        <div class="component-list" :aria-busy="props.busy">
          <div v-if="!sortedComponents.length" class="components-empty">
            <Boxes :size="25" aria-hidden="true" />
            <strong>Nenhum componente opcional</strong>
            <p>O equipamento pode continuar sem componentes. Adicione somente os itens necessários.</p>
          </div>
          <div v-for="component in sortedComponents" :key="component.id" class="component-row">
            <div class="component-symbol"><Layers3 :size="17" aria-hidden="true" /></div>
            <div class="component-row__name"><strong>{{ component.name }}</strong><span>Componente do modelo</span></div>
            <Badge :variant="component.active ? 'success' : 'secondary'">{{ component.active ? 'Ativo' : 'Inativo' }}</Badge>
            <VMenu>
              <template #activator="{ props: menuProps }">
                <VBtn
                  v-bind="menuProps"
                  variant="text"
                  size="small"
                  :icon="mdiDotsVertical"
                  :disabled="props.busy"
                  :loading="isComponentDeleting(component)"
                  :aria-label="`Ações para ${component.name}`"
                />
              </template>
              <VList density="compact" min-width="185" class="action-menu">
                <VListItem :prepend-icon="mdiPencilOutline" title="Renomear" @click="emit('renameComponent', component)" />
                <VListItem :prepend-icon="mdiPower" :title="component.active ? 'Desativar' : 'Reativar'" @click="emit('toggleComponent', component)" />
                <VListItem :prepend-icon="mdiTrashCanOutline" title="Excluir" class="delete-menu-item" @click="emit('removeComponent', component)" />
              </VList>
            </VMenu>
          </div>
        </div>
        <p class="section-footer">Cada componente pertence a este modelo. Não é necessário vinculá-lo separadamente às áreas. Itens inativos não serão oferecidos em novos cadastros.</p>
      </section>
    </article>
  </section>
</template>

<style scoped>
.master-detail { display: flex; min-width: 0; flex-direction: column; }
.detail-card { min-width: 0; flex: 1; overflow: hidden; border: 1px solid #e5eaf1; border-radius: 15px; box-shadow: 0 5px 24px rgb(35 58 88 / 4%); }
.detail-state { display: grid; flex: 1; justify-items: center; align-content: center; gap: 11px; min-height: 420px; padding: 34px; text-align: center; }
.detail-state h2 { margin: 0; color: #213758; font-size: 18px; }
.detail-state p { max-width: 440px; margin: 0; color: #7c8ba0; font-size: 13px; line-height: 1.6; }
.state-icon { display: grid; width: 58px; height: 58px; place-items: center; border-radius: 16px; background: #edf3fa; color: #577ba5; }
.detail-header { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 14px; padding: 24px 26px 22px; border-bottom: 1px solid #edf0f5; }
.detail-header__identity { min-width: 0; flex: 1 1 360px; }
.eyebrow { margin: 0 0 6px; color: #5879a6; font-size: 10.5px; font-weight: 800; letter-spacing: .09em; text-transform: uppercase; }
.detail-header__title { display: flex; flex-wrap: wrap; align-items: center; gap: 9px; }
.detail-header__title h2 { margin: 0; min-width: 0; overflow-wrap: anywhere; color: #20324a; font-size: clamp(19px, 1.7vw, 24px); line-height: 1.25; letter-spacing: -.025em; font-weight: 800; }
.equipment-summary { display: flex; flex-wrap: wrap; gap: 8px; margin: 9px 0 0; color: #718198; font-size: 11.5px; }
.header-actions { display: flex; flex-wrap: wrap; gap: 8px; }
.action-menu { padding: 5px; border: 1px solid #e4eaf2; border-radius: 11px; }
:deep(.delete-menu-item .v-list-item-title) { color: #ba4945; }
.relationship-note { display: flex; align-items: flex-start; gap: 12px; margin: 22px 26px 2px; border: 1px solid #dbe6f3; border-radius: 12px; padding: 14px 16px; background: #f5f8fc; }
.relationship-note__icon { display: grid; flex: 0 0 33px; width: 33px; height: 33px; place-items: center; border-radius: 9px; background: #e5eef9; color: #426899; }
.relationship-note h3 { margin: 1px 0 5px; color: #29476b; font-size: 12.5px; font-weight: 800; }
.relationship-note p { margin: 0; color: #4d6179; font-size: 12px; line-height: 1.55; }
.relationship-note span { display: block; margin-top: 5px; color: #7a8aa0; font-size: 11px; line-height: 1.5; }
.config-section { padding: 25px 26px; }
.config-section--components { border-top: 1px solid #edf0f5; }
.section-heading { display: flex; align-items: flex-start; gap: 11px; margin-bottom: 19px; }
.step-marker { display: grid; flex: 0 0 28px; width: 28px; height: 28px; place-items: center; border-radius: 9px; background: #eaf1fa; color: #304f7e; font-size: 13px; font-weight: 800; }
.section-heading__copy { min-width: 0; flex: 1; }
.section-heading h3 { margin: 2px 0 4px; color: #243a55; font-size: 15px; font-weight: 800; }
.section-heading p { margin: 0; color: #7c899c; font-size: 11.5px; line-height: 1.5; }
.section-heading > :last-child:not(.section-heading__copy) { margin-top: 3px; }
.area-editor { border: 1px solid #e4eaf1; border-radius: 12px; padding: 17px; background: #fbfcfe; }
.area-editor__label { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 7px; margin-bottom: 10px; color: #334b67; font-size: 12px; font-weight: 750; }
.area-editor__hint { color: #8b98a9; font-size: 10.5px; font-weight: 500; }
.selected-area-list { display: flex; min-height: 62px; flex-wrap: wrap; align-items: flex-start; align-content: center; gap: 8px; margin-bottom: 13px; border: 1px dashed #d5dfeb; border-radius: 9px; padding: 12px; background: #fff; }
.selected-area { max-width: 100%; }
.selected-area :deep(.v-chip__content) { overflow: hidden; text-overflow: ellipsis; }
.unassigned-state { display: flex; align-items: center; gap: 8px; color: #8694a6; font-size: 12px; }
.unassigned-state svg { flex-shrink: 0; }
.area-picker { display: flex; align-items: center; gap: 9px; }
.area-picker > :first-child { min-width: 0; flex: 1; }
.area-picker :deep(.v-field) { background: #fff; }
.field-help { margin: 6px 0 0; color: #8391a4; font-size: 10.8px; line-height: 1.45; }
.warning-note { display: flex; gap: 8px; margin: 11px 0 0; border-radius: 9px; padding: 10px; background: #fff6e7; color: #836020; font-size: 11px; line-height: 1.5; }
.warning-note svg { flex-shrink: 0; }
.save-strip { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 12px; margin-top: 14px; border: 1px solid #e8d1a5; border-radius: 11px; padding: 12px 14px; background: #fff9ed; }
.save-strip__copy { display: grid; align-items: center; grid-template-columns: 8px 1fr; column-gap: 9px; }
.save-strip__copy strong { color: #7b5d25; font-size: 11.5px; }
.save-strip__copy small { grid-column: 2; color: #927a51; font-size: 10.5px; }
.change-dot { width: 8px; height: 8px; border-radius: 50%; background: #cf963b; }
.save-strip__actions { display: flex; flex-wrap: wrap; gap: 7px; }
.component-form { display: flex; align-items: flex-start; gap: 9px; }
.component-form > :first-child { flex: 1; min-width: 0; }
.component-form > :last-child { margin-top: 3px; }
.component-list { display: grid; gap: 7px; margin-top: 12px; }
.component-row { display: flex; min-width: 0; align-items: center; gap: 12px; border: 1px solid #e8edf3; border-radius: 10px; padding: 12px 13px; background: #fff; }
.component-symbol { display: grid; flex: 0 0 34px; height: 34px; place-items: center; border-radius: 9px; background: #f0f4fa; color: #6884a6; }
.component-row__name { display: grid; min-width: 0; flex: 1; gap: 3px; }
.component-row__name strong { overflow-wrap: anywhere; color: #324963; font-size: 12px; font-weight: 750; line-height: 1.4; }
.component-row__name span { color: #92a0b0; font-size: 10px; }
.components-empty { display: grid; justify-items: center; gap: 8px; padding: 30px 18px; border: 1px dashed #d9e2ed; border-radius: 11px; color: #7890ae; text-align: center; }
.components-empty strong { color: #405a76; font-size: 12px; }
.components-empty p { max-width: 330px; margin: 0; color: #8c99a9; font-size: 11px; line-height: 1.55; }
.section-footer { margin: 13px 0 0; color: #8d9aab; font-size: 10.6px; line-height: 1.55; }
@media (max-width: 730px) {
  .detail-header, .config-section { padding: 18px; }
  .relationship-note { margin: 16px 18px 2px; }
  .area-picker { align-items: stretch; flex-direction: column; }
  .area-picker > :last-child:not(:first-child) { align-self: flex-start; }
}
@media (max-width: 530px) {
  .component-form { flex-direction: column; }
  .component-form > :first-child, .component-form > :last-child { width: 100%; }
  .component-row { gap: 7px; padding: 9px; }
  .component-symbol { display: none; }
  .component-row__name span { display: none; }
}
</style>
