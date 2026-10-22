<script setup lang="ts">
import { computed, ref, onMounted } from "vue";
import { Plus, Search, Upload } from "lucide-vue-next";

definePageMeta({ middleware: "admin" });
interface Area { id: string; name: string; isUnassigned: boolean; active: boolean }
interface Option { id: string; name: string; active: boolean }
interface Master { id: string; name: string; areaIds: string[]; components: Option[]; active: boolean; reviewFlags: string[] }
interface Catalog { areas: Area[]; equipments: Master[] }
interface SeedResult { areasNew: number; equipmentsNew: number; componentsNew: number; existing: number; dryRun: boolean }

const api = useApi();
const loading = ref(false);
const saving = ref(false);
const error = ref("");
const success = ref("");
const catalog = ref<Catalog>({ areas: [], equipments: [] });
const search = ref("");
const filterArea = ref("");
const selectedEquipment = ref("");
const newAreaName = ref("");
const newEquipmentName = ref("");
const newComponentName = ref("");
const importedFile = ref<File | null>(null);
const seedPreview = ref<SeedResult | null>(null);
const draftAreas = ref<string[]>([]);

const areas = computed(() => catalog.value.areas.filter((a) => a.active));
const models = computed(() => catalog.value.equipments.filter((item) =>
  (filterArea === undefined || !filterArea.value || (filterArea.value === "unassigned"
    ? !item.areaIds.length || item.areaIds.some((id) => catalog.value.areas.find(a => a.id === id)?.isUnassigned)
    : item.areaIds.includes(filterArea.value)))
  && item.name.toLocaleLowerCase("pt-BR").includes(search.value.trim().toLocaleLowerCase("pt-BR")),
));
const editing = computed(() => catalog.value.equipments.find(item => item.id === selectedEquipment.value));

async function load(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    catalog.value = await api.get<Catalog>("/master-catalog", { include_inactive: true });
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "Erro ao carregar Catálogo Mestre.";
  } finally {
    loading.value = false;
  }
}
onMounted(() => { void load(); });

function selectModel(item: Master): void {
  selectedEquipment.value = item.id;
  draftAreas.value = [...item.areaIds];
}
function onFileChange(event: Event): void {
  const input = event.target as HTMLInputElement;
  importedFile.value = input.files?.[0] ?? null;
  seedPreview.value = null;
}
async function importSeed(apply: boolean): Promise<void> {
  if (!importedFile.value || saving.value) return;
  saving.value = true;
  error.value = "";
  success.value = "";
  try {
    const data = JSON.parse(await importedFile.value.text()) as unknown;
    const result = await api.post<SeedResult>(
      "/master-catalog/seed?dry_run=" + (!apply), data,
    );
    seedPreview.value = result;
    success.value = apply ? "Catálogo carregado com sucesso." : "Pré-validação concluída. Confira os totais antes de aplicar.";
    if (apply) {
      await load();
      importedFile.value = null;
    }
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "Seed inválido.";
  } finally { saving.value = false; }
}
async function applySeed(): Promise<void> {
  if (!seedPreview.value || !importedFile.value) return;
  if (!confirm("Aplicar o seed no catálogo deste ambiente? Os equipamentos de obras existentes não serão alterados.")) return;
  await importSeed(true);
}
async function addArea(): Promise<void> {
  if (!newAreaName.value.trim() || saving.value) return;
  saving.value = true; error.value = "";
  try {
    await api.post("/master-catalog/areas", { name: newAreaName.value.trim() });
    newAreaName.value = "";
    await load();
  } catch (caught) { error.value = String(caught); }
  finally { saving.value = false; }
}
async function addEquipment(): Promise<void> {
  if (!newEquipmentName.value.trim() || saving.value) return;
  saving.value = true; error.value = "";
  try {
    await api.post("/master-catalog/equipments", { name: newEquipmentName.value.trim(), areaIds: [] });
    newEquipmentName.value = "";
    await load();
  } catch (caught) { error.value = String(caught); }
  finally { saving.value = false; }
}
async function addComponent(): Promise<void> {
  if (!newComponentName.value.trim() || !editing.value || saving.value) return;
  saving.value = true; error.value = "";
  try {
    await api.post("/master-catalog/equipments/" + editing.value.id + "/components", { name: newComponentName.value.trim() });
    newComponentName.value = "";
    await load();
  } catch (caught) { error.value = String(caught); }
  finally { saving.value = false; }
}
async function rename(path: string, previous: string): Promise<void> {
  const name = prompt("Novo nome:", previous)?.trim();
  if (!name || name === previous) return;
  try { await api.patch(path, { name }); await load(); success.value = "Nome atualizado."; }
  catch (caught) { error.value = String(caught); }
}
async function toggle(path: string, active: boolean): Promise<void> {
  if (active && !confirm("Desativar este registro no Catálogo Mestre? Obras já criadas não serão alteradas.")) return;
  try { await api.patch(path, { active: !active }); await load(); }
  catch (caught) { error.value = String(caught); }
}
function toggleArea(area: Area): void {
  if (area.isUnassigned) {
    draftAreas.value = draftAreas.value.includes(area.id) ? [] : [area.id];
    return;
  }
  const selected = new Set(draftAreas.value.filter(id => !catalog.value.areas.find(a => a.id === id)?.isUnassigned));
  if (selected.has(area.id)) selected.delete(area.id);
  else selected.add(area.id);
  draftAreas.value = [...selected];
}
async function saveAreas(): Promise<void> {
  if (!editing.value || saving.value) return;
  saving.value = true;
  try {
    await api.put("/master-catalog/equipments/" + editing.value.id + "/areas", { areaIds: draftAreas.value });
    success.value = "Áreas atualizadas. Obras existentes não foram modificadas.";
    await load();
  } catch (caught) { error.value = String(caught); }
  finally { saving.value = false; }
}
</script>

<template>
  <section class="master-admin">
    <BackLink to="/equipamentos">Voltar aos equipamentos</BackLink>
    <ReferenceSectionHeader title="Catálogo Mestre de Equipamentos"
      description="Gerencie os modelos globais e seus componentes opcionais, sem vinculação a obras ou TAGs." />
    <p v-if="error" class="alert" role="alert">{{ error }}</p>
    <p v-if="success" class="notice" role="status">{{ success }}</p>

    <div class="surface block">
      <h2><Upload :size="18" /> Importar seed do Catálogo Mestre</h2>
      <p>Faça uma pré-validação do arquivo JSON v2.1. O arquivo fica fora do repositório público.</p>
      <input type="file" accept=".json,application/json" aria-label="Arquivo do seed do catálogo" @change="onFileChange" />
      <div class="actions">
        <button :disabled="!importedFile || saving" @click="importSeed(false)">Validar seed (sem gravar)</button>
        <button :disabled="!seedPreview || saving || !importedFile" class="primary" @click="applySeed">Aplicar seed</button>
      </div>
      <p v-if="seedPreview" class="notice">
        {{ seedPreview.areasNew }} áreas, {{ seedPreview.equipmentsNew }} equipamentos e
        {{ seedPreview.componentsNew }} componentes novos · {{ seedPreview.existing }} existentes.
      </p>
    </div>

    <div class="surface block">
      <h2>Áreas</h2>
      <div class="inline-form">
        <input v-model="newAreaName" placeholder="Nome da nova área" maxlength="160" />
        <button :disabled="saving || !newAreaName.trim()" @click="addArea"><Plus :size="15" /> Criar área</button>
      </div>
      <div class="chips">
        <span v-for="area in catalog.areas" :key="area.id" class="chip" :class="{ inactive: !area.active }">
          {{ area.name }}
          <button type="button" :aria-label="'Renomear ' + area.name"
            :disabled="area.isUnassigned" @click="rename('/master-catalog/areas/' + area.id, area.name)">Editar</button>
          <button v-if="!area.isUnassigned" type="button" @click="toggle('/master-catalog/areas/' + area.id, area.active)">{{ area.active ? "Desativar" : "Ativar" }}</button>
        </span>
      </div>
    </div>

    <div class="master-grid">
      <div class="surface block">
        <h2>Equipamentos ({{ models.length }})</h2>
        <div class="inline-form">
          <input v-model="newEquipmentName" placeholder="Novo equipamento mestre" maxlength="200" />
          <button :disabled="saving || !newEquipmentName.trim()" @click="addEquipment"><Plus :size="15" /> Adicionar</button>
        </div>
        <div class="inline-form">
          <label class="search"><Search :size="15" /><input v-model="search" placeholder="Buscar equipamento" aria-label="Buscar equipamento mestre" /></label>
          <select v-model="filterArea" aria-label="Filtrar área">
            <option value="">Todas as áreas</option>
            <option value="unassigned">Sem área definida</option>
            <option v-for="area in areas.filter(a => !a.isUnassigned)" :key="area.id" :value="area.id">{{ area.name }}</option>
          </select>
        </div>
        <p v-if="loading">Carregando catálogo...</p>
        <div class="equipment-list">
          <button v-for="item in models" :key="item.id" type="button" class="equipment-button"
            :class="{ chosen: item.id === selectedEquipment }" @click="selectModel(item)">
            <span>{{ item.name }}</span><small>{{ item.components.length }} componentes</small>
          </button>
        </div>
      </div>

      <div class="surface block" v-if="editing">
        <h2>{{ editing.name }}</h2>
        <div class="actions">
          <button @click="rename('/master-catalog/equipments/' + editing.id, editing.name)">Editar nome</button>
          <button @click="toggle('/master-catalog/equipments/' + editing.id, editing.active)">{{ editing.active ? "Desativar" : "Ativar" }}</button>
        </div>
        <h3>Áreas associadas</h3>
        <p>A classificação mestre não modifica a EAP de nenhuma obra.</p>
        <div class="area-checks">
          <label v-for="area in areas" :key="area.id">
            <input type="checkbox" :checked="draftAreas.includes(area.id)" @change="toggleArea(area)" />
            {{ area.name }}
          </label>
        </div>
        <button class="primary" :disabled="saving" @click="saveAreas">Salvar áreas</button>
        <h3>Componentes opcionais</h3>
        <div class="inline-form">
          <input v-model="newComponentName" maxlength="500" placeholder="Novo componente" />
          <button :disabled="saving || !newComponentName.trim()" @click="addComponent"><Plus :size="15" /> Adicionar</button>
        </div>
        <div class="components">
          <div v-for="item in editing.components" :key="item.id" class="component-row">
            <span :class="{ inactive: !item.active }">{{ item.name }}</span>
            <button @click="rename('/master-catalog/components/' + item.id, item.name)">Editar</button>
            <button @click="toggle('/master-catalog/components/' + item.id, item.active)">{{ item.active ? "Desativar" : "Ativar" }}</button>
          </div>
        </div>
      </div>
      <div v-else class="surface block muted">Selecione um equipamento para administrar suas áreas e componentes.</div>
    </div>
  </section>
</template>

<style scoped>
.master-admin { display: grid; gap: 18px; color: #273e5a; }
.surface { background: #fff; border: 1px solid #e1e8f1; border-radius: 14px; }
.block { padding: 19px; display: flex; flex-direction: column; gap: 13px; min-width: 0; }
h2 { display: flex; align-items: center; gap: 9px; font-size: 16px; font-weight: 800; margin: 0; }
h3 { font-size: 13px; font-weight: 800; margin: 10px 0 0; }
p { font-size: 13px; color: #677a93; margin: 0; }
.alert { background: #fff2f1; border-radius: 8px; padding: 10px; color: #aa4038; }
.notice { background: #eef5eb; border-radius: 8px; padding: 10px; color: #3f6b39; }
input:not([type=checkbox]):not([type=file]), select { min-width: 0; border: 1px solid #d7e0ed; border-radius: 8px; padding: 9px 11px; background: white; font-size: 13px; }
button { display: inline-flex; align-items: center; justify-content: center; gap: 6px; border: 1px solid #d3deeb; background: #fff; color: #304f7e; border-radius: 8px; padding: 8px 10px; cursor: pointer; font-size: 12px; font-weight: 700; }
button:disabled { opacity: .45; cursor: not-allowed; }
.primary { color: #fff; background: #304f7e; border-color: #304f7e; }
.actions, .inline-form, .chips { display: flex; flex-wrap: wrap; gap: 8px; }
.inline-form input { flex: 1; }
.chip { display: inline-flex; gap: 5px; align-items: center; border: 1px solid #e0e7f1; border-radius: 9px; padding: 4px 6px 4px 10px; font-size: 12px; }
.chip button, .component-row button { padding: 4px 6px; font-size: 11px; }
.inactive { opacity: .5; text-decoration: line-through; }
.master-grid { display: grid; grid-template-columns: minmax(280px, 1fr) minmax(300px, 1.2fr); gap: 16px; align-items: start; }
.search { display: flex; align-items: center; gap: 6px; flex: 1; }
.search input { width: 100%; }
.equipment-list { max-height: 550px; overflow-y: auto; display: grid; gap: 4px; }
.equipment-button { justify-content: space-between; text-align: left; }
.equipment-button.chosen { background: #e8f1fc; border-color: #92b2d9; }
.equipment-button small { color: #71849a; }
.area-checks { display: grid; grid-template-columns: repeat(auto-fit,minmax(170px,1fr)); gap: 6px; max-height: 175px; overflow-y: auto; }
.area-checks label { display: flex; align-items: center; gap: 7px; font-size: 12px; }
.components { max-height: 400px; overflow-y: auto; display: grid; gap: 6px; }
.component-row { display: flex; align-items: center; gap: 5px; padding: 6px 0; border-bottom: 1px solid #edf1f6; }
.component-row span { margin-right: auto; font-size: 12px; }
.muted { color: #8391a5; font-size: 13px; }
@media (max-width: 850px) { .master-grid { grid-template-columns: 1fr; } }
</style>
