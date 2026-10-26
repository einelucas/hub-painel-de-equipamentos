<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import MasterCatalogAreasModal from "~/components/master-catalog/MasterCatalogAreasModal.vue";
import MasterCatalogBrowser from "~/components/master-catalog/MasterCatalogBrowser.vue";
import MasterCatalogDetail from "~/components/master-catalog/MasterCatalogDetail.vue";
import MasterCatalogFormModal from "~/components/master-catalog/MasterCatalogFormModal.vue";
import MasterCatalogHeader from "~/components/master-catalog/MasterCatalogHeader.vue";
import MasterCatalogImportModal from "~/components/master-catalog/MasterCatalogImportModal.vue";
import BackLink from "~/components/ui/BackLink.vue";
import { useConfirm } from "~/composables/useConfirm";
import type {
  MasterArea,
  MasterCatalog,
  MasterCatalogRenameTarget,
  MasterComponent,
  MasterEquipment,
} from "~/types/masterCatalog";
import {
  activeRealAreas,
  buildAreaMap,
  findUnassignedArea,
  isAreaDraftDirty,
} from "~/utils/masterCatalog";

definePageMeta({ middleware: "admin" });

const api = useApi();
const { confirm } = useConfirm();

const loading = ref(false);
const saving = ref(false);
const savingAreas = ref(false);
const deletingId = ref("");
const error = ref("");
const success = ref("");
let loadVersion = 0;

const catalog = ref<MasterCatalog>({ areas: [], equipments: [] });
const selectedEquipment = ref("");
const draftAreas = ref<string[]>([]);
const search = ref("");
const filterArea = ref("");

const createOpen = ref(false);
const createError = ref("");
const areasOpen = ref(false);
const newAreaName = ref("");
const areaError = ref("");
const newComponentName = ref("");
const componentError = ref("");
const importOpen = ref(false);
const renameTarget = ref<MasterCatalogRenameTarget | null>(null);
const renameError = ref("");

const equipments = computed(() => catalog.value.equipments);
const areas = computed(() => catalog.value.areas);
const areaMap = computed(() => buildAreaMap(areas.value));
const realAreas = computed(() => activeRealAreas(areas.value));
const unassignedArea = computed(() => findUnassignedArea(areas.value));
const editing = computed(
  () => equipments.value.find((item) => item.id === selectedEquipment.value) ?? null,
);
const activeEquipmentCount = computed(
  () => equipments.value.filter((item) => item.active).length,
);
const totalComponents = computed(() =>
  equipments.value.reduce((total, item) => total + item.components.length, 0),
);
const areasDirty = computed(() =>
  editing.value ? isAreaDraftDirty(editing.value, draftAreas.value) : false,
);
const createDefaultArea = computed<MasterArea | null>(() => {
  if (!filterArea.value) return null;
  if (filterArea.value === "unassigned") return unassignedArea.value;
  return realAreas.value.find((area) => area.id === filterArea.value) ?? null;
});
const createHint = computed(() => {
  if (!createDefaultArea.value) {
    return "As áreas e os componentes podem ser ajustados logo depois.";
  }
  return `O novo equipamento será associado à área "${createDefaultArea.value.name}" pelo filtro atual. Você poderá alterar depois.`;
});
const renameTitle = computed(() =>
  renameTarget.value ? `Renomear ${renameTarget.value.kind}` : "Renomear registro",
);
const renameLabel = computed(() => {
  if (renameTarget.value?.kind === "área") return "Nome da área";
  if (renameTarget.value?.kind === "componente") return "Nome do componente";
  return "Nome do equipamento";
});

function messageFrom(caught: unknown, fallback: string): string {
  return caught instanceof Error ? caught.message : fallback;
}

function applySelection(item: MasterEquipment): void {
  selectedEquipment.value = item.id;
  draftAreas.value = [...item.areaIds];
  newComponentName.value = "";
  componentError.value = "";
}

function syncDraftWithCatalog(): void {
  const knownIds = new Set(areas.value.map((area) => area.id));
  if (draftAreas.value.some((id) => !knownIds.has(id))) {
    draftAreas.value = draftAreas.value.filter((id) => knownIds.has(id));
  }
}

function syncSelection(): void {
  if (!equipments.value.length) {
    selectedEquipment.value = "";
    draftAreas.value = [];
    return;
  }
  const current = equipments.value.find((item) => item.id === selectedEquipment.value);
  if (!current) {
    const first = equipments.value[0];
    if (first) applySelection(first);
    return;
  }
  syncDraftWithCatalog();
}

async function load(): Promise<void> {
  const version = ++loadVersion;
  loading.value = true;
  error.value = "";
  try {
    const result = await api.get<MasterCatalog>("/master-catalog", {
      include_inactive: true,
    });
    if (version !== loadVersion) return;
    catalog.value = result;
    syncSelection();
  } catch (caught) {
    if (version !== loadVersion) return;
    error.value = messageFrom(caught, "Erro ao carregar Catálogo Mestre.");
  } finally {
    if (version === loadVersion) loading.value = false;
  }
}

onMounted(() => {
  void load();
});

function clearFilters(): void {
  search.value = "";
  filterArea.value = "";
}

async function selectEquipment(item: MasterEquipment): Promise<void> {
  if (saving.value || item.id === selectedEquipment.value) return;
  if (areasDirty.value) {
    const discard = await confirm({
      title: "Descartar alterações?",
      message: `As alterações de áreas de "${editing.value?.name ?? "equipamento"}" serão perdidas.`,
      detail: "Salve as áreas antes de trocar de equipamento para manter a alteração.",
      confirmLabel: "Descartar",
      tone: "primary",
      icon: "warning",
    });
    if (!discard) return;
  }
  applySelection(item);
}

function openCreate(): void {
  if (saving.value) return;
  createError.value = "";
  error.value = "";
  createOpen.value = true;
}

function closeCreate(): void {
  if (saving.value) return;
  createOpen.value = false;
  createError.value = "";
}

async function createEquipment(name: string): Promise<void> {
  if (saving.value) return;
  if (areasDirty.value && editing.value) {
    const discard = await confirm({
      title: "Descartar alterações?",
      message: `As alterações de áreas de "${editing.value.name}" serão perdidas ao abrir o novo equipamento.`,
      detail: "Salve as áreas antes de criar um novo equipamento para manter a alteração.",
      confirmLabel: "Descartar",
      tone: "primary",
      icon: "warning",
    });
    if (!discard) return;
  }
  const defaultArea = createDefaultArea.value;
  saving.value = true;
  createError.value = "";
  error.value = "";
  success.value = "";
  try {
    const created = await api.post<{ id: string }>("/master-catalog/equipments", {
      name,
      areaIds: defaultArea ? [defaultArea.id] : [],
    });
    createOpen.value = false;
    search.value = "";
    await load();
    if (error.value) return;
    const item = equipments.value.find((entry) => entry.id === created.id);
    if (item) applySelection(item);
    success.value = defaultArea
      ? `Equipamento criado e associado à área "${defaultArea.name}".`
      : "Equipamento criado. Associe áreas e componentes no painel ao lado.";
  } catch (caught) {
    createError.value = messageFrom(caught, "Não foi possível criar o equipamento.");
  } finally {
    saving.value = false;
  }
}

function openAreas(): void {
  if (saving.value) return;
  areaError.value = "";
  error.value = "";
  areasOpen.value = true;
}

function closeAreas(): void {
  if (saving.value) return;
  areasOpen.value = false;
  areaError.value = "";
}

async function addArea(name: string): Promise<void> {
  if (saving.value) return;
  saving.value = true;
  areaError.value = "";
  success.value = "";
  try {
    await api.post("/master-catalog/areas", { name });
    newAreaName.value = "";
    await load();
  } catch (caught) {
    areaError.value = messageFrom(caught, "Não foi possível criar a área.");
  } finally {
    saving.value = false;
  }
}

async function saveAreas(): Promise<void> {
  if (!editing.value || saving.value) return;
  const areaIds = draftAreas.value.filter((id) => areaMap.value.get(id)?.active);
  saving.value = true;
  savingAreas.value = true;
  error.value = "";
  success.value = "";
  try {
    await api.put(`/master-catalog/equipments/${editing.value.id}/areas`, { areaIds });
    await load();
    if (error.value) return;
    if (editing.value) draftAreas.value = [...editing.value.areaIds];
    success.value = "Áreas atualizadas. Obras existentes não foram modificadas.";
  } catch (caught) {
    error.value = messageFrom(caught, "Não foi possível salvar as áreas.");
  } finally {
    saving.value = false;
    savingAreas.value = false;
  }
}

function discardAreas(): void {
  if (!editing.value || saving.value) return;
  draftAreas.value = [...editing.value.areaIds];
}

function toggleAreaDraft(areaId: string): void {
  if (saving.value) return;
  const area = areaMap.value.get(areaId);
  if (!area) return;
  if (area.isUnassigned) {
    draftAreas.value = draftAreas.value.includes(areaId) ? [] : [areaId];
    return;
  }
  const selected = new Set(
    draftAreas.value.filter((id) => !areaMap.value.get(id)?.isUnassigned),
  );
  if (selected.has(areaId)) selected.delete(areaId);
  else selected.add(areaId);
  draftAreas.value = [...selected];
}

async function addComponent(name: string): Promise<void> {
  if (!editing.value || saving.value) return;
  saving.value = true;
  componentError.value = "";
  error.value = "";
  success.value = "";
  try {
    await api.post(`/master-catalog/equipments/${editing.value.id}/components`, { name });
    newComponentName.value = "";
    await load();
  } catch (caught) {
    componentError.value = messageFrom(
      caught,
      "Não foi possível adicionar o componente.",
    );
  } finally {
    saving.value = false;
  }
}

function openRename(target: MasterCatalogRenameTarget): void {
  if (saving.value) return;
  renameError.value = "";
  if (target.kind === "área") areaError.value = "";
  if (target.kind === "componente") componentError.value = "";
  renameTarget.value = target;
}

function closeRename(): void {
  if (saving.value) return;
  renameTarget.value = null;
  renameError.value = "";
}

async function submitRename(name: string): Promise<void> {
  const target = renameTarget.value;
  if (!target || saving.value) return;
  if (name === target.previous) {
    closeRename();
    return;
  }
  saving.value = true;
  renameError.value = "";
  error.value = "";
  success.value = "";
  try {
    await api.patch(target.path, { name });
    await load();
    renameTarget.value = null;
    if (error.value) return;
    success.value = "Nome atualizado.";
  } catch (caught) {
    renameError.value = messageFrom(caught, "Não foi possível renomear.");
  } finally {
    saving.value = false;
  }
}

function renameEquipment(): void {
  if (!editing.value) return;
  openRename({
    path: `/master-catalog/equipments/${editing.value.id}`,
    previous: editing.value.name,
    kind: "equipamento",
    maxLength: 200,
  });
}

function renameComponent(component: MasterComponent): void {
  openRename({
    path: `/master-catalog/components/${component.id}`,
    previous: component.name,
    kind: "componente",
    maxLength: 500,
  });
}

function renameArea(area: MasterArea): void {
  openRename({
    path: `/master-catalog/areas/${area.id}`,
    previous: area.name,
    kind: "área",
    maxLength: 160,
  });
}

async function toggleActive(
  path: string,
  active: boolean,
  name: string,
  fromAreaModal = false,
): Promise<void> {
  if (saving.value) return;
  if (active) {
    const confirmed = await confirm({
      title: "Desativar registro",
      message: `Deseja desativar "${name}"?`,
      detail:
        "Obras já criadas não serão alteradas; o item deixa de aparecer para novas obras.",
      confirmLabel: "Desativar",
      tone: "primary",
      icon: "warning",
    });
    if (!confirmed) return;
  }
  saving.value = true;
  if (fromAreaModal) areaError.value = "";
  else error.value = "";
  success.value = "";
  try {
    await api.patch(path, { active: !active });
    await load();
  } catch (caught) {
    const message = messageFrom(caught, "Não foi possível alterar o status do registro.");
    if (fromAreaModal) areaError.value = message;
    else error.value = message;
  } finally {
    saving.value = false;
  }
}

function toggleEquipment(): void {
  if (!editing.value) return;
  void toggleActive(
    `/master-catalog/equipments/${editing.value.id}`,
    editing.value.active,
    editing.value.name,
  );
}

function toggleComponent(component: MasterComponent): void {
  void toggleActive(
    `/master-catalog/components/${component.id}`,
    component.active,
    component.name,
  );
}

function toggleAreaRecord(area: MasterArea): void {
  void toggleActive(
    `/master-catalog/areas/${area.id}`,
    area.active,
    area.name,
    true,
  );
}

async function removeRecord(
  path: string,
  name: string,
  kind: string,
  fromAreaModal = false,
): Promise<void> {
  if (saving.value) return;
  const confirmed = await confirm({
    title: "Excluir do Catálogo Mestre",
    message: `Deseja excluir ${kind} "${name}"?`,
    detail:
      "Esta ação não pode ser desfeita. O item sai apenas do Catálogo Mestre; obras já criadas não são alteradas.",
    confirmLabel: "Excluir",
    tone: "danger",
    icon: "trash",
  });
  if (!confirmed) return;
  saving.value = true;
  deletingId.value = path;
  if (fromAreaModal) areaError.value = "";
  else error.value = "";
  success.value = "";
  try {
    await api.delete(path);
    if (path === `/master-catalog/equipments/${selectedEquipment.value}`) {
      selectedEquipment.value = "";
    }
    await load();
    if (error.value) return;
    success.value = "Registro excluído do Catálogo Mestre.";
  } catch (caught) {
    const message = messageFrom(caught, "Não foi possível excluir o registro.");
    if (fromAreaModal) areaError.value = message;
    else error.value = message;
  } finally {
    saving.value = false;
    deletingId.value = "";
  }
}

function removeEquipment(): void {
  if (!editing.value) return;
  void removeRecord(
    `/master-catalog/equipments/${editing.value.id}`,
    editing.value.name,
    "o equipamento",
  );
}

function removeComponent(component: MasterComponent): void {
  void removeRecord(
    `/master-catalog/components/${component.id}`,
    component.name,
    "o componente",
  );
}

function removeArea(area: MasterArea): void {
  void removeRecord(`/master-catalog/areas/${area.id}`, area.name, "a área", true);
}

function openImport(): void {
  if (saving.value) return;
  error.value = "";
  importOpen.value = true;
}

function closeImport(): void {
  if (saving.value) return;
  importOpen.value = false;
}

async function imported(): Promise<void> {
  importOpen.value = false;
  clearFilters();
  await load();
  if (error.value) return;
  success.value = "Catálogo atualizado com o seed importado.";
}
</script>

<template>
  <section class="master-admin">
    <BackLink class="page-back" to="/equipamentos">Voltar aos equipamentos</BackLink>

    <MasterCatalogHeader
      :equipment-count="equipments.length"
      :active-equipment-count="activeEquipmentCount"
      :area-count="realAreas.length"
      :component-count="totalComponents"
      :busy="saving"
      @create="openCreate"
      @manage-areas="openAreas"
      @import-seed="openImport"
    />

    <p v-if="error" class="notice error" role="alert">{{ error }}</p>
    <p v-if="success" class="notice" role="status">{{ success }}</p>

    <div class="master-layout">
      <MasterCatalogBrowser
        v-model:search="search"
        v-model:filter-area="filterArea"
        :equipments="equipments"
        :areas="areas"
        :selected-id="selectedEquipment"
        :loading="loading"
        :busy="saving"
        @select="selectEquipment"
        @clear-filters="clearFilters"
      />

      <MasterCatalogDetail
        v-model:new-component-name="newComponentName"
        :equipment="editing"
        :areas="areas"
        :draft-areas="draftAreas"
        :areas-dirty="areasDirty"
        :loading="loading"
        :busy="saving"
        :saving-areas="savingAreas"
        :deleting-id="deletingId"
        :component-error="componentError"
        @rename-equipment="renameEquipment"
        @toggle-equipment="toggleEquipment"
        @remove-equipment="removeEquipment"
        @toggle-area="toggleAreaDraft"
        @save-areas="saveAreas"
        @discard-areas="discardAreas"
        @add-component="addComponent"
        @rename-component="renameComponent"
        @toggle-component="toggleComponent"
        @remove-component="removeComponent"
      />
    </div>
  </section>

  <MasterCatalogFormModal
    :open="createOpen"
    title="Novo equipamento"
    label="Nome do equipamento"
    placeholder="Ex.: Bomba centrífuga"
    :hint="createHint"
    confirm-label="Criar equipamento"
    :busy="saving"
    :error="createError"
    @close="closeCreate"
    @submit="createEquipment"
  />

  <MasterCatalogFormModal
    :open="Boolean(renameTarget)"
    :title="renameTitle"
    :label="renameLabel"
    :initial-value="renameTarget?.previous ?? ''"
    :max-length="renameTarget?.maxLength ?? 200"
    :busy="saving"
    :error="renameError"
    @close="closeRename"
    @submit="submitRename"
  />

  <MasterCatalogAreasModal
    v-model:new-area-name="newAreaName"
    :open="areasOpen"
    :areas="areas"
    :equipments="equipments"
    :busy="saving"
    :deleting-id="deletingId"
    :error="areaError"
    @close="closeAreas"
    @add="addArea"
    @rename="renameArea"
    @toggle="toggleAreaRecord"
    @remove="removeArea"
  />

  <MasterCatalogImportModal
    :open="importOpen"
    @close="closeImport"
    @imported="imported"
  />
</template>

<style scoped>
.master-admin {
  display: grid;
  gap: 16px;
  color: #273e5a;
}

.master-admin > .notice {
  margin: 0;
}

.master-layout {
  display: grid;
  grid-template-columns: minmax(310px, 380px) minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}

@media (max-width: 1180px) {
  .master-layout {
    grid-template-columns: 1fr;
  }
}
</style>
