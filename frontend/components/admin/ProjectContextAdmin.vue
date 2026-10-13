<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { Check, Pencil, Plus, X } from "lucide-vue-next";
import type {
  CatalogItem,
  CatalogList,
  EapNodeItem,
  ProjectAdminTarget,
  Unit,
} from "~/types/equipment";
import { toOptions } from "~/utils/selectOptions";
import SearchableSelect from "~/components/ui/SearchableSelect.vue";

/**
 * Configuração da obra: ProjectContexts de uma Unidade + resumo de preparação.
 *
 * Usa só os endpoints de catálogo existentes. As ações "Gerenciar ..." não
 * duplicam CRUDs: pedem ao painel para abrir a seção que já existe.
 */
const props = defineProps<{ unitId: string }>();
const emit = defineEmits<{
  "update:unitId": [value: string];
  changed: [];
  navigate: [target: ProjectAdminTarget];
}>();

const api = useApi();
const auth = useAuthStore();
const canManage = computed(() => auth.can("catalogs:manage"));
const canManageAccess = computed(() => auth.can("users:manage"));

const units = ref<Unit[]>([]);
const contexts = ref<CatalogItem[]>([]);
const selectedId = ref("");
const loadingUnits = ref(true);
const loading = ref(false);
const saving = ref(false);
const togglingId = ref<string | null>(null);
let contextsVersion = 0;
let summaryVersion = 0;
const error = ref("");
const formError = ref("");
const mode = ref<"idle" | "create" | "edit">("idle");
const form = reactive({ code: "", name: "", active: true });

const summary = reactive({ loading: false, error: "", eapNodes: 0, disciplines: 0, workPackages: 0 });

const selectedUnit = computed(() => units.value.find((unit) => unit.id === props.unitId) ?? null);
const selected = computed(() => contexts.value.find((item) => item.id === selectedId.value) ?? null);

async function loadUnits(): Promise<void> {
  loadingUnits.value = true;
  error.value = "";
  try {
    units.value = (await api.get<CatalogList<Unit>>("/units")).items;
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "Não foi possível carregar as unidades.";
  } finally {
    loadingUnits.value = false;
  }
}

async function loadContexts(): Promise<void> {
  const version = ++contextsVersion;
  contexts.value = [];
  mode.value = "idle";
  if (!props.unitId) {
    selectedId.value = "";
    loading.value = false;
    return;
  }
  loading.value = true;
  error.value = "";
  try {
    // Administração vê ativos e inativos (exige catalogs:manage); telas operacionais seguem só com ativos.
    const result = (
      await api.get<CatalogList<CatalogItem>>(`/units/${props.unitId}/project-contexts`, {
        include_inactive: "true",
      })
    ).items;
    if (version !== contextsVersion) return;
    contexts.value = result;
    if (!contexts.value.some((item) => item.id === selectedId.value)) {
      selectedId.value = contexts.value[0]?.id ?? "";
    }
  } catch (caught) {
    if (version !== contextsVersion) return;
    error.value = caught instanceof Error ? caught.message : "Não foi possível carregar os contextos.";
  } finally {
    if (version === contextsVersion) loading.value = false;
  }
}

/** Resumo de preparação: só contagens das APIs existentes, sem regra nova. */
async function loadSummary(): Promise<void> {
  const version = ++summaryVersion;
  summary.error = "";
  if (!props.unitId || !selectedId.value) {
    summary.loading = false;
    return;
  }
  summary.loading = true;
  try {
    const [eapNodes, disciplines, workPackages] = await Promise.all([
      api.get<CatalogList<EapNodeItem>>("/eap-nodes", { active: true }),
      api.get<CatalogList<CatalogItem>>("/disciplines"),
      api.get<CatalogList<CatalogItem>>("/work-packages"),
    ]);
    if (version !== summaryVersion) return;
    summary.eapNodes = eapNodes.items.length;
    summary.disciplines = disciplines.items.filter((item) => item.active).length;
    summary.workPackages = workPackages.items.length;
  } catch (caught) {
    if (version !== summaryVersion) return;
    summary.error = caught instanceof Error ? caught.message : "Não foi possível carregar o resumo.";
  } finally {
    if (version === summaryVersion) summary.loading = false;
  }
}

const unitOptions = computed(() =>
  toOptions(units.value, (unit) => `${unit.name}${unit.active ? "" : " (inativa)"}`),
);

function selectUnit(value: string): void {
  emit("update:unitId", value);
}

function startCreate(): void {
  mode.value = "create";
  formError.value = "";
  Object.assign(form, { code: "", name: "", active: true });
}

function startEdit(item: CatalogItem): void {
  selectedId.value = item.id;
  mode.value = "edit";
  formError.value = "";
  Object.assign(form, {
    code: item.code ?? "",
    name: item.name,
    active: item.active,
  });
}

function cancel(): void {
  mode.value = "idle";
  formError.value = "";
}

async function submit(): Promise<void> {
  if (saving.value) return;
  const code = form.code.trim();
  const name = form.name.trim();
  if (!name) {
    formError.value = "Informe o nome.";
    return;
  }
  saving.value = true;
  formError.value = "";
  // A obra precisa só de nome; o código é opcional e não compõe a EAP.
  const payload: Record<string, unknown> = { name };
  if (mode.value === "edit") payload.code = code || null;
  else if (code) payload.code = code;
  try {
    if (mode.value === "edit" && selected.value) {
      if (form.active !== selected.value.active) payload.active = form.active;
      await api.patch(`/project-contexts/${selected.value.id}`, payload);
    } else {
      const created = await api.post<CatalogItem>(`/units/${props.unitId}/project-contexts`, payload);
      if (created?.id) selectedId.value = created.id;
    }
    await loadContexts();
    emit("changed");
  } catch (caught) {
    formError.value = caught instanceof Error ? caught.message : "Não foi possível salvar.";
  } finally {
    saving.value = false;
  }
}

/**
 * Mesmo padrão dos catálogos: desativar pede confirmação; reativar não.
 * O contexto inativo continua nesta lista (visão administrativa) para ser reativado.
 */
async function toggleActive(item: CatalogItem): Promise<void> {
  const message = `Desativar "${item.name}"? Ele deixa de aparecer nos formulários, mas continua aqui para reativação.`;
  if (saving.value) return;
  if (item.active && !confirm(message)) return;
  saving.value = true;
  togglingId.value = item.id;
  error.value = "";
  try {
    await api.patch(`/project-contexts/${item.id}`, { active: !item.active });
    await loadContexts();
    emit("changed");
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "Não foi possível alterar a situação.";
  } finally {
    saving.value = false;
    togglingId.value = null;
  }
}

onMounted(loadUnits);
watch(() => props.unitId, loadContexts, { immediate: true });
watch(selectedId, loadSummary);
</script>

<template>
  <section class="projects" data-testid="project-context-admin">
    <header class="projects-head">
      <div>
        <h3>Projetos</h3>
        <p>{{ selectedUnit ? `Obras de ${selectedUnit.name}` : "Obras cadastradas por unidade" }}</p>
      </div>
      <div class="projects-toolbar">
      <div class="field unit-picker">
        <span>Unidade</span>
        <SearchableSelect
          :model-value="props.unitId"
          :options="unitOptions"
          :clearable="false"
          :disabled="loadingUnits"
          label="Unidade"
          placeholder="Buscar unidade"
          empty-label="Selecione"
          test-id="project-unit"
          @change="selectUnit"
        />
      </div>
      <button
        v-if="canManage && props.unitId"
        type="button"
        class="btn small primary"
        :disabled="saving"
        data-testid="project-new"
        @click="startCreate"
      >
        <Plus :size="14" /> Novo contexto
      </button>
      </div>
    </header>

    <p v-if="loadingUnits" class="projects-hint"><span class="spinner spinner-small" /> Carregando unidades...</p>

    <div v-else-if="!props.unitId" class="projects-empty" data-testid="project-no-unit">
      <p>Selecione ou cadastre uma unidade antes de criar um contexto.</p>
      <button
        v-if="canManage"
        type="button"
        class="text-button"
        data-testid="project-goto-units"
        @click="emit('navigate', { section: 'catalogs', catalog: 'units' })"
      >
        Gerenciar unidades
      </button>
    </div>

    <template v-else>
      <form
        v-if="mode !== 'idle'"
        class="project-form"
        data-testid="project-form"
        @submit.prevent="submit"
      >
        <h4>{{ mode === "create" ? "Novo contexto de projeto" : "Editar contexto de projeto" }}</h4>
        <label class="field">
          <span>Código (opcional)</span>
          <input v-model="form.code" maxlength="60" data-testid="project-code">
        </label>
        <label class="field">
          <span>Nome *</span>
          <input v-model="form.name" maxlength="160" required data-testid="project-name">
        </label>
        <label v-if="mode === 'edit'" class="project-active">
          <input v-model="form.active" type="checkbox" data-testid="project-active">
          <span>Ativo</span>
        </label>
        <p v-else class="field-help project-create-note">O contexto é criado ativo.</p>
        <p v-if="formError" class="projects-error" role="alert">{{ formError }}</p>
        <div class="project-form-actions">
          <button type="button" class="btn small" @click="cancel"><X :size="13" /> Cancelar</button>
          <button type="submit" class="btn small primary" :disabled="saving" data-testid="project-save" :aria-busy="saving">
            <span v-if="saving" class="spinner-small" aria-hidden="true" /><Check v-else :size="13" /> {{ saving ? "Salvando..." : "Salvar" }}
          </button>
        </div>
      </form>

      <p v-if="loading" class="projects-hint"><span class="spinner spinner-small" /> Carregando contextos...</p>
      <p v-else-if="error" class="projects-error" role="alert">{{ error }}</p>
      <div v-else-if="contexts.length === 0" class="projects-empty" data-testid="project-empty">
        <p>Nenhum contexto de projeto nesta unidade.</p>
        <p v-if="canManage" class="field-help">Use "Novo contexto" para preparar uma obra.</p>
      </div>

      <div v-else class="projects-layout">
        <ul class="project-list" aria-label="Contextos de projeto">
          <li
            v-for="item in contexts"
            :key="item.id"
            :class="{ selected: item.id === selectedId, inactive: !item.active }"
            :data-testid="`project-item-${item.id}`"
          >
            <button type="button" class="project-card" @click="selectedId = item.id">
              <span v-if="item.code" class="project-code">{{ item.code }}</span>
              <span class="project-name">{{ item.name }}</span>
              <span class="project-meta">
                <span class="status" :class="item.active ? 'status--on' : 'status--off'">
                  {{ item.active ? "Ativo" : "Inativo" }}
                </span>
              </span>
            </button>
            <span v-if="canManage" class="project-actions">
              <button type="button" class="text-button" :disabled="saving" @click="startEdit(item)">
                <Pencil :size="12" /> Editar
              </button>
              <button type="button" class="text-button" :disabled="saving" :aria-busy="togglingId === item.id" @click="toggleActive(item)">
                <span v-if="togglingId === item.id" class="spinner-small" aria-hidden="true" />
                {{ togglingId === item.id ? "Salvando..." : item.active ? "Desativar" : "Reativar" }}
              </button>
            </span>
          </li>
        </ul>

        <aside v-if="selected" class="readiness" data-testid="project-readiness" aria-label="Preparação da obra">
          <h4>Preparação da obra</h4>
          <dl>
            <div>
              <dt>Unidade</dt>
              <dd>{{ selectedUnit?.name ?? "Configurada" }}</dd>
            </div>
            <div>
              <dt>Contexto</dt>
              <dd>{{ selected.code ? `${selected.code} · ` : "" }}{{ selected.active ? "Ativo" : "Inativo" }}</dd>
            </div>
            <template v-if="summary.loading">
              <div><dt>Catálogos</dt><dd><span class="spinner spinner-small" /></dd></div>
            </template>
            <template v-else-if="!summary.error">
              <div>
                <dt>Árvore EAP</dt>
                <dd data-testid="readiness-eap">{{ summary.eapNodes }} globais</dd>
              </div>
              <div>
                <dt>Disciplinas</dt>
                <dd data-testid="readiness-disciplines">{{ summary.disciplines }} ativas</dd>
              </div>
              <div>
                <dt>Work Packages</dt>
                <dd data-testid="readiness-work-packages">{{ summary.workPackages }} cadastrados</dd>
              </div>
            </template>
          </dl>
          <p v-if="summary.error" class="projects-error" role="alert">{{ summary.error }}</p>
          <p class="field-help">Resumo informativo. Não bloqueia o uso do contexto.</p>
          <div class="readiness-actions">
            <button
              v-if="canManage"
              type="button"
              class="text-button"
              data-testid="goto-areas"
              @click="emit('navigate', { section: 'catalogs', catalog: 'areas' })"
            >
              Gerenciar Árvore EAP
            </button>
            <button
              v-if="canManage"
              type="button"
              class="text-button"
              data-testid="goto-work-packages"
              @click="emit('navigate', { section: 'catalogs', catalog: 'workPackages' })"
            >
              Gerenciar Work Packages
            </button>
            <button
              v-if="canManageAccess"
              type="button"
              class="text-button"
              data-testid="goto-access"
              @click="emit('navigate', { section: 'access' })"
            >
              Gerenciar acessos
            </button>
          </div>
        </aside>
      </div>
    </template>
  </section>
</template>

<style scoped>
.projects { display: grid; gap: 14px; }
.projects-head { display: flex; flex-wrap: wrap; align-items: flex-end; justify-content: space-between; gap: 12px; padding-bottom: 12px; border-bottom: 1px solid var(--rule, #dde5ef); }
.projects-head h3 { margin: 0; color: var(--ink, #1f3352); font-size: 17px; font-weight: 800; letter-spacing: -0.01em; }
.projects-head p { margin: 2px 0 0; color: var(--muted, #6b7a8f); font-size: 12px; }
.projects-toolbar { display: flex; flex-wrap: wrap; align-items: flex-end; gap: 10px; }
.unit-picker { width: 260px; max-width: 100%; }
.projects-hint { display: flex; align-items: center; gap: 8px; margin: 0; color: var(--muted, #6b7a8f); font-size: 12px; }
.projects-error { margin: 0; color: var(--stop, #a4453a); font-size: 12px; font-weight: 700; }
.projects-empty { display: grid; justify-items: center; gap: 6px; border: 1px dashed var(--rule, #dde5ef); border-radius: 12px; padding: 24px; color: var(--muted, #6b7a8f); font-size: 12.5px; text-align: center; }
.projects-empty p { margin: 0; }

.project-form { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px 12px; border: 1px solid #c9d8ec; border-radius: 12px; padding: 14px; background: var(--wash, #f3f6fb); }
.project-form h4 { grid-column: 1 / -1; margin: 0; color: var(--ink, #1f3352); font-size: 12.5px; font-weight: 800; }
.project-form > .field:nth-of-type(2) { grid-column: span 2; }
.project-active { display: flex; align-items: center; gap: 8px; color: var(--ink, #1f3352); font-size: 12.5px; }
.project-create-note { align-self: center; margin: 0; }
.project-form .projects-error { grid-column: 1 / -1; }
.project-form-actions { display: flex; grid-column: 1 / -1; justify-content: flex-end; gap: 8px; }
.field-help { color: var(--muted, #6b7a8f); font-size: 11px; line-height: 1.4; }

.projects-layout { display: grid; grid-template-columns: minmax(0, 1.35fr) minmax(250px, 1fr); align-items: start; gap: 16px; }
.project-list { display: grid; margin: 0; padding: 0; gap: 8px; list-style: none; }
.project-list li {
  position: relative;
  display: grid;
  gap: 8px;
  border: 1px solid var(--rule, #dde5ef);
  border-radius: 12px;
  padding: 12px 14px;
  background: #fff;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}
.project-list li:hover { border-color: #c4d2e4; }
.project-list li.selected { border-color: var(--steel, #304f7e); box-shadow: 0 0 0 3px rgb(48 79 126 / 10%); }
.project-list li.inactive { background: #fafbfc; }
.project-list li.inactive .project-name { color: #9aa6b5; }
.project-card { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: center; gap: 2px 10px; border: 0; padding: 0; background: transparent; text-align: left; cursor: pointer; }
.project-card:focus-visible { outline: 2px solid var(--steel, #304f7e); outline-offset: 4px; border-radius: 6px; }
.project-code { grid-column: 1; color: var(--steel, #304f7e); font-family: var(--mono, monospace); font-size: 11.5px; font-weight: 700; }
.project-name { grid-column: 1; min-width: 0; overflow: hidden; color: var(--ink, #1f3352); font-size: 14px; font-weight: 800; text-overflow: ellipsis; white-space: nowrap; }
.project-meta { grid-column: 2; grid-row: 1 / span 2; }
.project-actions { display: flex; gap: 14px; border-top: 1px solid #edf1f6; padding-top: 8px; }
.status { display: inline-flex; align-items: center; gap: 5px; font-size: 11px; font-weight: 750; }
.status::before { width: 7px; height: 7px; border-radius: 999px; background: currentColor; content: ""; }
.status--on { color: var(--go, #3f7a2e); }
.status--off { color: #9aa6b5; }
.text-button { display: inline-flex; align-items: center; gap: 4px; border: 0; padding: 2px; background: transparent; color: var(--steel, #304f7e); font-size: 11.5px; font-weight: 750; cursor: pointer; }
.text-button:hover:not(:disabled) { text-decoration: underline; }

/* Preparação: checklist da obra selecionada */
.readiness { position: sticky; top: 0; display: grid; gap: 10px; border-radius: 12px; padding: 14px 16px; background: var(--wash, #f3f6fb); }
.readiness h4 { margin: 0; color: var(--ink, #1f3352); font-size: 12.5px; font-weight: 800; }
.readiness dl { display: grid; margin: 0; }
.readiness dl > div { display: flex; align-items: baseline; justify-content: space-between; gap: 10px; border-bottom: 1px solid var(--rule, #dde5ef); padding: 7px 0; font-size: 12px; }
.readiness dl > div:last-child { border-bottom: 0; }
.readiness dt { color: var(--muted, #6b7a8f); }
.readiness dd { margin: 0; color: var(--ink, #1f3352); font-family: var(--mono, monospace); font-size: 11.5px; font-weight: 700; text-align: right; }
.readiness-actions { display: grid; justify-items: start; gap: 4px; border-top: 1px solid var(--rule, #dde5ef); padding-top: 10px; }
@media (max-width: 760px) {
  .projects-layout { grid-template-columns: 1fr; }
  .readiness { position: static; }
  .project-form { grid-template-columns: 1fr; }
  .project-form > .field:nth-of-type(2) { grid-column: auto; }
}
@media (prefers-reduced-motion: reduce) { .project-list li { transition: none; } }
</style>
