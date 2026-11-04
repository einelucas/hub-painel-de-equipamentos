<script setup lang="ts">
import { mdiCheck, mdiClose, mdiPencilOutline, mdiPlus, mdiTrashCanOutline } from "@mdi/js";
import { computed, onMounted, reactive, ref, useId, watch } from "vue";
import type {
  CatalogItem,
  CatalogList,
  EapNodeItem,
  ProjectAdminTarget,
  Unit,
} from "~/types/equipment";
import { toOptions } from "~/utils/selectOptions";
import SearchableSelect from "~/components/ui/SearchableSelect.vue";
import AppModal from "~/components/ui/AppModal.vue";
import { VBtn } from "vuetify/components";
import { useConfirm } from "~/composables/useConfirm";
import { useProjectCreation } from "~/composables/useProjectCreation";

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
const { confirm } = useConfirm();
const creation = useProjectCreation();
const canManage = computed(() => auth.can("catalogs:manage"));
const canManageAccess = computed(() => auth.can("users:manage"));

const units = ref<Unit[]>([]);
const contexts = ref<CatalogItem[]>([]);
const selectedId = ref("");
const loadingUnits = ref(true);
const loading = ref(false);
const saving = ref(false);
const togglingId = ref<string | null>(null);
const deletingId = ref<string | null>(null);
interface DeletionImpact {
  projectContextId: string;
  projectContextName: string;
  records: Record<string, number>;
  totalRecords: number;
  contractFiles: number;
}
const deleteTarget = ref<CatalogItem | null>(null);
const deletionImpact = ref<DeletionImpact | null>(null);
const deletionConfirmation = ref("");
const loadingImpact = ref(false);
let contextsVersion = 0;
let summaryVersion = 0;
const error = ref("");
const formError = ref("");
const mode = ref<"idle" | "edit">("idle");
const form = reactive({ code: "", name: "", active: true });
const formId = `project-form-${useId()}`;
const formOpen = computed(() => mode.value !== "idle");
const formTitle = computed(() => "Editar obra");

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
  if (saving.value) return;
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
    if (selected.value) {
      if (form.active !== selected.value.active) payload.active = form.active;
      await api.patch(`/project-contexts/${selected.value.id}`, payload);
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
  if (saving.value) return;
  if (item.active) {
    const confirmed = await confirm({
      message: `Deseja desativar "${item.name}"?`,
      detail: "Ele deixa de aparecer nos formulários, mas continua aqui para reativação.",
      confirmLabel: "Desativar",
      tone: "primary",
    });
    if (!confirmed) return;
  }
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

async function prepareRemove(item: CatalogItem): Promise<void> {
  if (saving.value) return;
  deleteTarget.value = item;
  deletionConfirmation.value = "";
  deletionImpact.value = null;
  loadingImpact.value = true;
  error.value = "";
  try {
    const impact = await api.get<DeletionImpact>(
      `/project-contexts/${item.id}/deletion-impact`,
      undefined,
      { force: true },
    );
    deletionImpact.value = {
      ...impact,
      records: impact.records ?? {},
      totalRecords: impact.totalRecords ?? 0,
      contractFiles: impact.contractFiles ?? 0,
    };
  } catch (caught) {
    deleteTarget.value = null;
    error.value = caught instanceof Error ? caught.message : "Não foi possível calcular o impacto.";
  } finally {
    loadingImpact.value = false;
  }
}

function cancelRemove(): void {
  if (deletingId.value) return;
  deleteTarget.value = null;
  deletionImpact.value = null;
  deletionConfirmation.value = "";
}

async function remove(): Promise<void> {
  const item = deleteTarget.value;
  if (!item || saving.value || deletionConfirmation.value !== item.name) return;
  saving.value = true;
  deletingId.value = item.id;
  error.value = "";
  try {
    await api.delete(`/project-contexts/${item.id}`, {
      confirmationName: deletionConfirmation.value,
    });
    deleteTarget.value = null;
    deletionImpact.value = null;
    deletionConfirmation.value = "";
    await loadContexts();
    const moduleContext = useModuleContextStore();
    await Promise.all([moduleContext.loadProjectContexts(), moduleContext.loadEquipmentOptions()]);
    emit("changed");
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "Não foi possível excluir a obra.";
  } finally {
    saving.value = false;
    deletingId.value = null;
  }
}

onMounted(loadUnits);
watch(() => props.unitId, loadContexts, { immediate: true });
watch(selectedId, loadSummary);
watch(creation.createdRevision, loadContexts);
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
        <VBtn
          v-if="canManage && props.unitId"
          variant="flat"
          color="primary"
          :disabled="saving"
          data-testid="project-new"
          :prepend-icon="mdiPlus"
          @click="creation.openNewProject(props.unitId)"
        >
          Nova Obra
        </VBtn>
      </div>
    </header>

    <p v-if="loadingUnits" class="projects-hint"><span class="spinner spinner-small" /> Carregando unidades...</p>

    <div v-else-if="!props.unitId" class="projects-empty" data-testid="project-no-unit">
      <p>Selecione ou cadastre uma unidade antes de criar um contexto.</p>
      <VBtn
        v-if="canManage"
        type="button"
        class="text-button"
        data-testid="project-goto-units"
        variant="text"
        size="small"
        @click="emit('navigate', { section: 'catalogs', catalog: 'units' })"
      >
        Gerenciar unidades
      </VBtn>
    </div>

    <template v-else>
      <p v-if="loading" class="projects-hint"><span class="spinner spinner-small" /> Carregando contextos...</p>
      <VAlert v-else-if="error" class="projects-error" type="error" role="alert">{{ error }}</VAlert>
      <div v-else-if="contexts.length === 0" class="projects-empty" data-testid="project-empty">
        <p>Nenhum contexto de projeto nesta unidade.</p>
        <p v-if="canManage" class="field-help">Use "Nova Obra" para preparar uma obra.</p>
      </div>

      <div v-else class="projects-layout">
        <ul class="project-list" aria-label="Contextos de projeto">
          <li
            v-for="item in contexts"
            :key="item.id"
            :class="{ selected: item.id === selectedId, inactive: !item.active }"
            :data-testid="`project-item-${item.id}`"
          >
            <VBtn
              type="button"
              class="project-card"
              variant="text"
              block
              :aria-pressed="item.id === selectedId"
              :aria-label="`Selecionar contexto ${item.name}`"
              @click="selectedId = item.id"
            >
              <span class="project-identity">
                <span v-if="item.code" class="project-code">{{ item.code }}</span>
                <span class="project-name">{{ item.name }}</span>
              </span>
              <span class="project-meta">
                <span class="status" :class="item.active ? 'status--on' : 'status--off'">
                  {{ item.active ? "Ativo" : "Inativo" }}
                </span>
              </span>
            </VBtn>
            <span v-if="canManage" class="project-actions">
              <VBtn type="button" class="text-button" :disabled="saving" variant="text" size="small" :prepend-icon="mdiPencilOutline" @click="startEdit(item)">
                 Editar
              </VBtn>
              <VBtn type="button" class="text-button" :disabled="saving" :loading="togglingId === item.id" variant="text" :color="item.active ? 'secondary' : 'success'" size="small" @click="toggleActive(item)">
                {{ togglingId === item.id ? "Salvando..." : item.active ? "Desativar" : "Reativar" }}
              </VBtn>
              <VBtn type="button" class="text-button text-button--danger" :disabled="saving" :loading="deletingId === item.id" variant="tonal" color="error" size="small" :prepend-icon="!(deletingId === item.id) ? mdiTrashCanOutline : undefined" @click="prepareRemove(item)">

                {{ deletingId === item.id ? "Excluindo..." : "Excluir" }}
              </VBtn>
            </span>
          </li>
        </ul>

        <aside v-if="selected" class="readiness" data-testid="project-readiness" aria-label="Preparação da obra">
          <header class="readiness-head">
            <span>Contexto selecionado</span>
            <h4>Preparação da obra</h4>
            <p>{{ selected.name }}</p>
          </header>
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
          <VAlert v-if="summary.error" class="projects-error" type="error" role="alert">{{ summary.error }}</VAlert>
          <p class="field-help">Resumo informativo. Não bloqueia o uso do contexto.</p>
          <div class="readiness-actions">
            <VBtn
              v-if="canManage"
              type="button"
              class="text-button"
              data-testid="goto-areas"
              variant="text"
              size="small"
              @click="emit('navigate', { section: 'catalogs', catalog: 'areas' })"
            >
              Gerenciar Árvore EAP
            </VBtn>
            <VBtn
              v-if="canManage"
              type="button"
              class="text-button"
              data-testid="goto-work-packages"
              variant="text"
              size="small"
              @click="emit('navigate', { section: 'catalogs', catalog: 'workPackages' })"
            >
              Gerenciar Work Packages
            </VBtn>
            <VBtn
              v-if="canManageAccess"
              type="button"
              class="text-button"
              data-testid="goto-access"
              variant="text"
              size="small"
              @click="emit('navigate', { section: 'access' })"
            >
              Gerenciar acessos
            </VBtn>
          </div>
        </aside>
      </div>
    </template>
  </section>

  <AppModal
    v-if="props.unitId"
    :open="formOpen"
    :title="formTitle"
    :busy="saving"
    @close="cancel"
  >
    <form
      :id="formId"
      class="project-form"
      data-testid="project-form"
      @submit.prevent="submit"
    >
      <div class="field">
        <VTextField v-model="form.code" label="Código (opcional)" maxlength="60" data-testid="project-code" />
      </div>
      <div class="field">
        <VTextField v-model="form.name" label="Nome *" maxlength="160" required data-testid="project-name" />
      </div>
      <label class="project-active">
        <input v-model="form.active" type="checkbox" data-testid="project-active">
        <span>Ativo</span>
      </label>
      <VAlert v-if="formError" class="projects-error" type="error" role="alert">{{ formError }}</VAlert>
    </form>

    <template #actions>
      <VBtn size="small" variant="outlined" :disabled="saving" :prepend-icon="mdiClose" @click="cancel">
         Cancelar
      </VBtn>
      <VBtn
        type="submit"
        size="small"
        variant="flat"
        color="primary"
        :form="formId"
        :loading="saving"
        data-testid="project-save"
       :prepend-icon="!saving ? mdiCheck : undefined" :disabled="saving">

        {{ saving ? "Salvando..." : "Salvar" }}
      </VBtn>
    </template>
  </AppModal>

  <AppModal
    :open="Boolean(deleteTarget)"
    title="Excluir obra permanentemente"
    :busy="Boolean(deletingId)"
    @close="cancelRemove"
  >
    <div v-if="deleteTarget" class="delete-project" data-testid="project-delete-dialog">
      <VAlert type="error" variant="tonal">
        Esta operação é permanente. A obra <strong>{{ deleteTarget.name }}</strong> e todos os
        dados que pertencem exclusivamente a ela serão excluídos.
      </VAlert>
      <p v-if="loadingImpact" role="status">Calculando registros afetados...</p>
      <template v-else-if="deletionImpact">
        <p>
          <strong>{{ deletionImpact.totalRecords }}</strong> registro(s) serão afetados,
          incluindo <strong>{{ deletionImpact.records.equipments ?? 0 }}</strong> equipamento(s)
          e <strong>{{ deletionImpact.contractFiles }}</strong> arquivo(s) de contrato.
        </p>
        <VTextField
          v-model="deletionConfirmation"
          label="Digite o nome da obra para confirmar"
          :placeholder="deleteTarget.name"
          autocomplete="off"
          data-testid="project-delete-confirmation"
        />
      </template>
    </div>
    <template #actions>
      <VBtn variant="outlined" :disabled="Boolean(deletingId)" @click="cancelRemove">Cancelar</VBtn>
      <VBtn
        color="error"
        variant="tonal"
        :loading="Boolean(deletingId)"
        :disabled="loadingImpact || deletionConfirmation !== deleteTarget?.name"
        data-testid="project-delete-confirm"
        :prepend-icon="mdiTrashCanOutline"
        @click="remove"
      >
        Excluir permanentemente
      </VBtn>
    </template>
  </AppModal>
</template>

<style scoped>
.projects { display: grid; gap: 16px; padding-top: 2px; }
.delete-project { display: grid; gap: 16px; }
.delete-project p { margin: 0; color: var(--ink, #1f3352); line-height: 1.55; }
.projects-head { display: flex; flex-wrap: wrap; align-items: flex-end; justify-content: space-between; gap: 12px; padding-bottom: 12px; border-bottom: 1px solid var(--rule, #dde5ef); }
.projects-head h3 { margin: 0; color: var(--ink, #1f3352); font-size: 17px; font-weight: 800; letter-spacing: -0.01em; }
.projects-head p { margin: 2px 0 0; color: var(--muted, #6b7a8f); font-size: 12px; }
.projects-toolbar { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; padding-top: 4px; }
.unit-picker { width: 260px; max-width: 100%; }
.projects-hint { display: flex; align-items: center; gap: 8px; margin: 0; color: var(--muted, #6b7a8f); font-size: 12px; }
.projects-empty { display: grid; justify-items: center; gap: 6px; border: 1px dashed var(--rule, #dde5ef); border-radius: 12px; padding: 24px; color: var(--muted, #6b7a8f); font-size: 12.5px; text-align: center; }
.projects-empty p { margin: 0; }

.project-form { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px 16px; }
.project-form > .field:nth-of-type(2) { grid-column: span 2; }
.project-active { display: flex; align-items: center; gap: 8px; color: var(--ink, #1f3352); font-size: 12.5px; }
.project-create-note { align-self: center; margin: 0; }
.project-form > .v-alert { grid-column: 1 / -1; }
.field-help { color: var(--muted, #6b7a8f); font-size: 11px; line-height: 1.4; }

.projects-layout { display: grid; grid-template-columns: minmax(0, 1.35fr) minmax(250px, 1fr); align-items: start; gap: 16px; }
.project-list { display: grid; margin: 0; padding: 0; gap: 8px; list-style: none; }
.project-list li {
  position: relative;
  display: grid;
  overflow: hidden;
  border: 1px solid var(--rule, #dde5ef);
  border-radius: 12px;
  background: #fff;
  transition: border-color 0.15s ease, box-shadow 0.15s ease, background 0.15s ease;
}
.project-list li:hover { border-color: #c4d2e4; }
.project-list li.selected { border-color: var(--steel, #304f7e); background: #f8fafc; box-shadow: 0 0 0 3px rgb(48 79 126 / 9%); }
.project-list li.selected::before {
  position: absolute;
  z-index: 1;
  top: 10px;
  bottom: 10px;
  left: 0;
  width: 3px;
  border-radius: 0 3px 3px 0;
  background: var(--steel, #304f7e);
  content: "";
}
.project-list li.inactive { background: #fafbfc; }
.project-list li.inactive .project-name { color: #9aa6b5; }
.project-card { min-height: 62px; height: auto; border-color: transparent; border-radius: 0; padding: 10px 14px; }
.project-card :deep(.v-btn__content) { display: grid; width: 100%; grid-template-columns: minmax(0, 1fr) auto; align-items: center; gap: 10px; text-align: left; }
.project-identity { display: grid; min-width: 0; gap: 2px; }
.project-code { color: var(--steel, #304f7e); font-family: var(--mono, monospace); font-size: 10.5px; font-weight: 750; letter-spacing: 0.025em; }
.project-name { min-width: 0; overflow: hidden; color: var(--ink, #1f3352); font-size: 14px; font-weight: 750; text-overflow: ellipsis; white-space: nowrap; }
.project-actions { display: flex; flex-wrap: wrap; gap: 2px; border-top: 1px solid #e8edf4; padding: 7px 10px 8px; }
.project-actions :deep(.v-btn) { border-color: transparent; }
.status { display: inline-flex; align-items: center; gap: 5px; border-radius: 999px; padding: 3px 8px; background: var(--go-wash, #eaf4e5); font-size: 10.5px; font-weight: 750; }
.status::before { width: 7px; height: 7px; border-radius: 999px; background: currentColor; content: ""; }
.status--on { color: var(--go, #3f7a2e); }
.status--off { color: #6b7280; background: #eef0f3; }

/* Preparação: checklist da obra selecionada */
.readiness { position: sticky; top: 0; display: grid; gap: 10px; border: 1px solid var(--rule, #dde5ef); border-radius: 12px; padding: 15px 16px; background: #fff; box-shadow: 0 8px 24px rgb(31 51 82 / 6%); }
.readiness-head { display: grid; gap: 2px; border-bottom: 1px solid var(--rule, #dde5ef); padding-bottom: 11px; }
.readiness-head > span { color: var(--steel, #304f7e); font-size: 9.5px; font-weight: 800; letter-spacing: 0.06em; text-transform: uppercase; }
.readiness h4 { margin: 0; color: var(--ink, #1f3352); font-size: 12.5px; font-weight: 800; }
.readiness-head p { margin: 0; overflow: hidden; color: var(--muted, #6b7a8f); font-size: 11.5px; text-overflow: ellipsis; white-space: nowrap; }
.readiness dl { display: grid; margin: 0; }
.readiness dl > div { display: flex; align-items: baseline; justify-content: space-between; gap: 10px; border-bottom: 1px solid var(--rule, #dde5ef); padding: 7px 0; font-size: 12px; }
.readiness dl > div:last-child { border-bottom: 0; }
.readiness dt { color: var(--muted, #6b7a8f); }
.readiness dd { margin: 0; color: var(--ink, #1f3352); font-family: var(--mono, monospace); font-size: 11.5px; font-weight: 700; text-align: right; }
.readiness-actions { display: grid; justify-items: stretch; gap: 2px; border-top: 1px solid var(--rule, #dde5ef); padding-top: 8px; }
.readiness-actions :deep(.v-btn) { justify-content: flex-start; border-color: transparent; }
.readiness-actions :deep(.v-btn__content) { width: 100%; justify-content: flex-start; }
@media (max-width: 760px) {
  .projects-head { align-items: stretch; }
  .projects-toolbar, .unit-picker { width: 100%; }
  .projects-toolbar :deep(.v-btn) { flex: 1 1 auto; }
  .projects-layout { grid-template-columns: 1fr; }
  .readiness { position: static; }
  .project-form { grid-template-columns: 1fr; }
  .project-form > .field:nth-of-type(2) { grid-column: auto; }
}
@media (prefers-reduced-motion: reduce) { .project-list li { transition: none; } }
</style>
