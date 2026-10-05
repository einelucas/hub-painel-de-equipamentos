<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { Check, Pencil, Plus, X } from "lucide-vue-next";
import type { CatalogItem, CatalogList, ProjectAdminTarget, Unit } from "~/types/equipment";

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
const error = ref("");
const formError = ref("");
const mode = ref<"idle" | "create" | "edit">("idle");
const form = reactive({ code: "", name: "", eapPrefix: "", active: true });

const summary = reactive({ loading: false, error: "", areas: 0, areasActive: 0, disciplines: 0, workPackages: 0 });

/** Mesma regra do backend: só dígitos, como texto ("03" continua "03"). Nunca inferido. */
const EAP_PREFIX_PATTERN = /^\d+$/;

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
  contexts.value = [];
  mode.value = "idle";
  if (!props.unitId) {
    selectedId.value = "";
    return;
  }
  loading.value = true;
  error.value = "";
  try {
    // Administração vê ativos e inativos (exige catalogs:manage); telas operacionais seguem só com ativos.
    contexts.value = (
      await api.get<CatalogList<CatalogItem>>(`/units/${props.unitId}/project-contexts`, {
        include_inactive: "true",
      })
    ).items;
    if (!contexts.value.some((item) => item.id === selectedId.value)) {
      selectedId.value = contexts.value[0]?.id ?? "";
    }
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "Não foi possível carregar os contextos.";
  } finally {
    loading.value = false;
  }
}

/** Resumo de preparação: só contagens das APIs existentes, sem regra nova. */
async function loadSummary(): Promise<void> {
  summary.error = "";
  if (!props.unitId || !selectedId.value) return;
  summary.loading = true;
  try {
    const [areas, disciplines, workPackages] = await Promise.all([
      api.get<CatalogList<CatalogItem>>("/areas", { unit_id: props.unitId }),
      api.get<CatalogList<CatalogItem>>("/disciplines"),
      api.get<CatalogList<CatalogItem>>("/work-packages", { project_context_id: selectedId.value }),
    ]);
    summary.areas = areas.items.length;
    summary.areasActive = areas.items.filter((item) => item.active).length;
    summary.disciplines = disciplines.items.filter((item) => item.active).length;
    summary.workPackages = workPackages.items.length;
  } catch (caught) {
    summary.error = caught instanceof Error ? caught.message : "Não foi possível carregar o resumo.";
  } finally {
    summary.loading = false;
  }
}

function selectUnit(event: Event): void {
  emit("update:unitId", (event.target as HTMLSelectElement).value);
}

function startCreate(): void {
  mode.value = "create";
  formError.value = "";
  Object.assign(form, { code: "", name: "", eapPrefix: "", active: true });
}

function startEdit(item: CatalogItem): void {
  selectedId.value = item.id;
  mode.value = "edit";
  formError.value = "";
  Object.assign(form, {
    code: item.code ?? "",
    name: item.name,
    eapPrefix: item.eapPrefix ?? "",
    active: item.active,
  });
}

function cancel(): void {
  mode.value = "idle";
  formError.value = "";
}

async function submit(): Promise<void> {
  const code = form.code.trim();
  const name = form.name.trim();
  const eapPrefix = form.eapPrefix.trim();
  if (!code || !name) {
    formError.value = "Informe código e nome.";
    return;
  }
  if (eapPrefix && !EAP_PREFIX_PATTERN.test(eapPrefix)) {
    formError.value = "Prefixo EAP deve conter só dígitos (ex.: 03).";
    return;
  }
  saving.value = true;
  formError.value = "";
  // Vazio = ainda não definido: envia null, nunca "" e nunca um valor calculado.
  const payload: Record<string, unknown> = { code, name, eapPrefix: eapPrefix || null };
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
  if (item.active && !confirm(message)) return;
  saving.value = true;
  error.value = "";
  try {
    await api.patch(`/project-contexts/${item.id}`, { active: !item.active });
    await loadContexts();
    emit("changed");
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "Não foi possível alterar a situação.";
  } finally {
    saving.value = false;
  }
}

onMounted(loadUnits);
watch(() => props.unitId, loadContexts, { immediate: true });
watch(selectedId, loadSummary);
</script>

<template>
  <section class="projects" data-testid="project-context-admin">
    <div class="projects-toolbar">
      <label class="field unit-picker">
        <span>Unidade</span>
        <select
          :value="props.unitId"
          :disabled="loadingUnits"
          data-testid="project-unit"
          @change="selectUnit"
        >
          <option value="">Selecione</option>
          <option v-for="unit in units" :key="unit.id" :value="unit.id">
            {{ unit.code }} · {{ unit.name }}{{ unit.active ? "" : " (inativa)" }}
          </option>
        </select>
      </label>
      <button
        v-if="canManage && props.unitId"
        type="button"
        class="btn small"
        :disabled="saving"
        data-testid="project-new"
        @click="startCreate"
      >
        <Plus :size="14" /> Novo contexto
      </button>
    </div>

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
          <span>Código *</span>
          <input v-model="form.code" maxlength="60" required data-testid="project-code">
        </label>
        <label class="field">
          <span>Nome *</span>
          <input v-model="form.name" maxlength="160" required data-testid="project-name">
        </label>
        <label class="field">
          <span>Prefixo EAP</span>
          <input
            v-model="form.eapPrefix"
            type="text"
            maxlength="10"
            inputmode="numeric"
            placeholder="Não definido"
            data-testid="project-eap-prefix"
          >
          <small class="field-help">
            O prefixo é definido oficialmente para o projeto/fase e não é gerado automaticamente.
          </small>
        </label>
        <label v-if="mode === 'edit'" class="project-active">
          <input v-model="form.active" type="checkbox" data-testid="project-active">
          <span>Ativo</span>
        </label>
        <p v-else class="field-help project-create-note">O contexto é criado ativo.</p>
        <p v-if="formError" class="projects-error" role="alert">{{ formError }}</p>
        <div class="project-form-actions">
          <button type="button" class="btn small" @click="cancel"><X :size="13" /> Cancelar</button>
          <button type="submit" class="btn small primary" :disabled="saving" data-testid="project-save">
            <Check :size="13" /> {{ saving ? "Salvando..." : "Salvar" }}
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
              <span class="project-code">{{ item.code }}</span>
              <span class="project-name">{{ item.name }}</span>
              <span class="project-meta">
                <span class="eap-chip" :class="{ 'eap-chip--empty': !item.eapPrefix }" data-testid="project-item-eap">
                  Prefixo EAP {{ item.eapPrefix ?? "não definido" }}
                </span>
                <span class="status" :class="item.active ? 'status--on' : 'status--off'">
                  {{ item.active ? "Ativo" : "Inativo" }}
                </span>
              </span>
            </button>
            <span v-if="canManage" class="project-actions">
              <button type="button" class="text-button" :disabled="saving" @click="startEdit(item)">
                <Pencil :size="12" /> Editar
              </button>
              <button type="button" class="text-button" :disabled="saving" @click="toggleActive(item)">
                {{ item.active ? "Desativar" : "Reativar" }}
              </button>
            </span>
          </li>
        </ul>

        <aside v-if="selected" class="readiness" data-testid="project-readiness" aria-label="Preparação da obra">
          <h4>Preparação</h4>
          <dl>
            <div>
              <dt>Unidade</dt>
              <dd>{{ selectedUnit ? `${selectedUnit.code} · ${selectedUnit.name}` : "Configurada" }}</dd>
            </div>
            <div>
              <dt>Contexto</dt>
              <dd>{{ selected.code }} · {{ selected.active ? "Ativo" : "Inativo" }}</dd>
            </div>
            <div>
              <dt>Prefixo EAP</dt>
              <dd data-testid="readiness-eap">{{ selected.eapPrefix ? `Definido (${selected.eapPrefix})` : "Não definido" }}</dd>
            </div>
            <template v-if="summary.loading">
              <div><dt>Catálogos</dt><dd><span class="spinner spinner-small" /></dd></div>
            </template>
            <template v-else-if="!summary.error">
              <div>
                <dt>Áreas</dt>
                <dd data-testid="readiness-areas">{{ summary.areasActive }} ativas · {{ summary.areas }} cadastradas</dd>
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
              Gerenciar áreas
            </button>
            <button
              v-if="canManage"
              type="button"
              class="text-button"
              data-testid="goto-work-packages"
              @click="emit('navigate', { section: 'catalogs', catalog: 'workPackages', contextId: selected.id })"
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
.projects { display: grid; gap: 12px; padding: 4px 0 14px; }
.projects-toolbar { display: flex; flex-wrap: wrap; align-items: flex-end; justify-content: space-between; gap: 10px; }
.unit-picker { flex: 1 1 240px; max-width: 360px; }
.projects-hint { display: flex; align-items: center; gap: 8px; margin: 0; color: #8b96a5; font-size: 12px; }
.projects-error { margin: 0; color: #a4453a; font-size: 12px; font-weight: 700; }
.projects-empty { display: grid; justify-items: start; gap: 4px; border: 1px dashed #dbe2ec; border-radius: 10px; padding: 14px; color: #65748a; font-size: 12.5px; }
.projects-empty p { margin: 0; }
.project-form { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; border: 1px solid #e4e9f0; border-radius: 10px; padding: 12px; background: #f8fafc; }
.project-form h4 { grid-column: 1 / -1; margin: 0; color: #2b3e58; font-size: 12.5px; font-weight: 800; }
.project-form > .field:nth-of-type(2) { grid-column: span 2; }
.project-active { display: flex; align-items: center; gap: 8px; color: #2b3e58; font-size: 12.5px; }
.project-create-note { align-self: center; margin: 0; }
.project-form .projects-error { grid-column: 1 / -1; }
.project-form-actions { display: flex; grid-column: 1 / -1; justify-content: flex-end; gap: 8px; }
.field-help { color: #8b96a5; font-size: 11px; line-height: 1.35; }
.projects-layout { display: grid; grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr); align-items: start; gap: 12px; }
.project-list { display: grid; margin: 0; padding: 0; gap: 6px; list-style: none; }
.project-list li { display: grid; gap: 4px; border: 1px solid #e4e9f0; border-radius: 10px; padding: 8px 10px; background: #fff; }
.project-list li.selected { border-color: #b9cde8; background: #f5f9fe; }
.project-list li.inactive .project-name { color: #8b96a5; }
.project-card { display: grid; grid-template-columns: auto minmax(0, 1fr); align-items: center; gap: 2px 8px; border: 0; padding: 0; background: transparent; text-align: left; }
.project-card:focus-visible { outline: 2px solid #304f7e; outline-offset: 2px; border-radius: 6px; }
.project-code { border-radius: 5px; background: #eef2f7; padding: 2px 6px; color: #53647a; font-size: 10.5px; font-weight: 800; }
.project-name { min-width: 0; overflow: hidden; color: #2b3e58; font-size: 12.5px; font-weight: 750; text-overflow: ellipsis; white-space: nowrap; }
.project-meta { display: flex; flex-wrap: wrap; grid-column: 1 / -1; gap: 6px; }
.project-actions { display: flex; justify-content: flex-end; gap: 10px; }
.eap-chip { border-radius: 999px; background: #e8f1fc; padding: 3px 8px; color: #27456f; font-size: 10.5px; font-weight: 750; }
.eap-chip--empty { background: #f4f6f9; color: #7a879a; }
.status { border-radius: 999px; padding: 3px 8px; font-size: 10.5px; font-weight: 750; }
.status--on { background: #eaf4e5; color: #477a32; }
.status--off { background: #eef2f7; color: #6b7a8f; }
.text-button { display: inline-flex; align-items: center; gap: 4px; border: 0; padding: 2px; background: transparent; color: #304f7e; font-size: 11.5px; font-weight: 750; }
.readiness { display: grid; gap: 8px; border: 1px solid #e4e9f0; border-radius: 10px; padding: 10px 12px; background: #f8fafc; }
.readiness h4 { margin: 0; color: #2b3e58; font-size: 12.5px; font-weight: 800; }
.readiness dl { display: grid; margin: 0; gap: 5px; }
.readiness dl > div { display: flex; justify-content: space-between; gap: 10px; font-size: 12px; }
.readiness dt { color: #7a879a; }
.readiness dd { margin: 0; color: #2b3e58; font-weight: 700; text-align: right; }
.readiness-actions { display: flex; flex-wrap: wrap; gap: 4px 12px; }
.spinner-small { width: 14px; height: 14px; border-width: 2px; }
@media (max-width: 620px) {
  .projects-layout { grid-template-columns: 1fr; }
  .project-form { grid-template-columns: 1fr; }
  .project-form > .field:nth-of-type(2) { grid-column: auto; }
}
</style>
