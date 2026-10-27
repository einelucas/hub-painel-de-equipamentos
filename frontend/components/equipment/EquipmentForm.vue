<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { Pencil } from "lucide-vue-next";
import Button from "~/components/ui/Button.vue";
import CurrencyInput from "~/components/ui/CurrencyInput.vue";
import SearchableMultiSelect from "~/components/ui/SearchableMultiSelect.vue";
import SearchableSelect from "~/components/ui/SearchableSelect.vue";
import { DEFAULT_ORIGIN, originOptions } from "~/utils/origin";
import type {
  CatalogItem,
  CatalogList,
  EapNodeItem,
  Equipment,
  Responsible,
} from "~/types/equipment";

const props = defineProps<{
  unitId: string;
  equipment?: Equipment | null;
}>();

const emit = defineEmits<{
  saved: [equipment: Equipment];
  cancel: [];
}>();

const api = useApi();
const auth = useAuthStore();

const contexts = ref<CatalogItem[]>([]);
const eapNodes = ref<EapNodeItem[]>([]);
const disciplines = ref<CatalogItem[]>([]);
const criticalityLabels = ref<CatalogItem[]>([]);
const workPackages = ref<CatalogItem[]>([]);
const responsibles = ref<Responsible[]>([]);

const loading = ref(true);
const saving = ref(false);
const error = ref("");
const showEapAdmin = ref(false);
const showCriticalityAdmin = ref(false);
const reloadingEap = ref(false);

const form = reactive({
  name: props.equipment?.name ?? "",
  projectContextId: props.equipment?.projectContext.id ?? "",
  origin: props.equipment?.origin ?? DEFAULT_ORIGIN,
  startupAt: props.equipment?.startupAt ?? "",
  disciplineId: props.equipment?.discipline?.id ?? "",
  eapNodeId: props.equipment?.eapNode?.id ?? "",

  // Relação N:N com pacotes de trabalho.
  workPackageIds: props.equipment?.workPackages.map((item) => item.id) ?? [],

  criticalityLabelId: props.equipment?.criticalityLabel?.id ?? "",
  capexEstimated: props.equipment?.capexEstimated?.toString() ?? "",
  responsibleUserId: props.equipment?.responsibleUser?.id ?? "",
  projectTotalValue: props.equipment?.projectTotalValue?.toString() ?? "",
  contractualDeliveryStart: props.equipment?.contractualDeliveryStart ?? "",
  contractualDeliveryEnd: props.equipment?.contractualDeliveryEnd ?? "",
});

const contextOptions = computed(() =>
  contexts.value.map((item) => ({
    id: item.id,
    label: item.code ? `${item.code} · ${item.name}` : item.name,
  })),
);
// Lista fixa do domínio, acrescida do valor atual quando ele estiver fora do
// vocabulário (registros antigos do Monday, ex.: "Importado").
const originSelectOptions = computed(() =>
  originOptions(form.origin).map((option) => ({ id: option, label: option })),
);
const eapOptions = computed(() =>
  eapNodes.value.map((item) => ({
    id: item.id,
    label: `${item.code} · ${item.name}`,
    description: item.level === "PROCESS" ? "Processo" : "Área",
  })),
);
const disciplineOptions = computed(() =>
  disciplines.value.map((item) => ({
    id: item.id,
    label: item.code ? `${item.code} · ${item.name}` : item.name,
    searchText: [item.code, item.name].filter(Boolean).join(" "),
  })),
);
const criticalityOptions = computed(() =>
  criticalityLabels.value.map((item) => ({
    id: item.id,
    label: item.name,
    searchText: item.name,
  })),
);
const workPackageOptions = computed(() =>
  workPackages.value.map((item) => ({
    id: item.id,
    label:
      item.code && item.name !== item.code
        ? `${item.code} · ${item.name}`
        : (item.code ?? item.name),
    description: item.description?.trim() || "WP sem descrição",
    searchText: [item.code, item.name, item.description].filter(Boolean).join(" "),
  })),
);
const responsibleOptions = computed(() =>
  responsibles.value.map((item) => ({
    id: item.id,
    label: item.name,
    description: item.email,
    searchText: `${item.name} ${item.email}`,
  })),
);

async function loadWorkPackages(): Promise<void> {
  workPackages.value = (await api.get<CatalogList<CatalogItem>>("/work-packages")).items;
}

async function loadEapNodes(): Promise<void> {
  const candidates = (
    await api.get<CatalogList<EapNodeItem>>("/eap-nodes", { active: true })
  ).items;
  eapNodes.value = candidates.filter(
    (item) => item.active && (item.level === "PROCESS" || item.level === "AREA"),
  );
  if (!eapNodes.value.some((item) => item.id === form.eapNodeId)) {
    form.eapNodeId = "";
  }
}

async function loadCriticalityLabels(): Promise<void> {
  criticalityLabels.value = (
    await api.get<CatalogList<CatalogItem>>("/criticality-labels")
  ).items;
  if (!form.criticalityLabelId && props.equipment?.criticality) {
    const legacy = props.equipment.criticality.trim().toLocaleLowerCase("pt-BR");
    form.criticalityLabelId =
      criticalityLabels.value.find(
        (item) => item.name.trim().toLocaleLowerCase("pt-BR") === legacy,
      )?.id ?? "";
  }
}

async function eapCatalogChanged(): Promise<void> {
  if (reloadingEap.value) return;
  reloadingEap.value = true;
  try {
    await loadEapNodes();
  } finally {
    reloadingEap.value = false;
  }
}

async function loadCatalogs(): Promise<void> {
  loading.value = true;

  try {
    const [contextResult, disciplineResult, responsibleResult] =
      await Promise.all([
        api.get<CatalogList<CatalogItem>>(
          `/units/${props.unitId}/project-contexts`,
        ),
        api.get<CatalogList<CatalogItem>>("/disciplines"),
        api.get<CatalogList<Responsible>>("/responsibles", {
          unit_id: props.unitId,
        }),
      ]);

    contexts.value = contextResult.items;
    disciplines.value = disciplineResult.items;
    responsibles.value = responsibleResult.items;

    if (
      form.responsibleUserId &&
      !responsibles.value.some((item) => item.id === form.responsibleUserId)
    ) {
      form.responsibleUserId = "";
    }

    if (!form.projectContextId && contexts.value.length === 1) {
      form.projectContextId = contexts.value[0]!.id;
    }

    await Promise.all([loadEapNodes(), loadWorkPackages(), loadCriticalityLabels()]);
  } catch (caught) {
    error.value =
      caught instanceof Error
        ? caught.message
        : "Não foi possível carregar os catálogos.";
  } finally {
    loading.value = false;
  }
}

async function submit(): Promise<void> {
  if (saving.value) return;
  if (!form.name.trim() || !form.projectContextId) {
    error.value = "Informe o nome e o contexto do equipamento.";
    return;
  }

  saving.value = true;
  error.value = "";

  const payload: Record<string, unknown> = {
    name: form.name.trim(),
    projectContextId: form.projectContextId,
    origin: form.origin || null,
    startupAt: form.startupAt || null,
    disciplineId: form.disciplineId || null,
    eapNodeId: form.eapNodeId || null,
    workPackageIds: form.workPackageIds,
    criticalityLabelId: form.criticalityLabelId || null,
    capexEstimated:
      form.capexEstimated === "" ? null : Number(form.capexEstimated),
    responsibleUserId: form.responsibleUserId || null,
    projectTotalValue:
      form.projectTotalValue === "" ? null : Number(form.projectTotalValue),
    contractualDeliveryStart: form.contractualDeliveryStart || null,
    contractualDeliveryEnd: form.contractualDeliveryEnd || null,
  };

  try {
    const result = props.equipment
      ? await api.patch<Equipment>(`/equipments/${props.equipment.id}`, payload)
      : await api.post<Equipment>("/equipments", payload);

    emit("saved", result);
  } catch (caught) {
    error.value =
      caught instanceof Error
        ? caught.message
        : "Não foi possível salvar o equipamento.";
  } finally {
    saving.value = false;
  }
}

onMounted(loadCatalogs);
</script>

<template>
  <div v-if="loading" class="form-loading" role="status">
    <span class="spinner" />
    Carregando catálogos...
  </div>

  <form v-else class="equipment-form" @submit.prevent="submit">
    <p v-if="error" class="notice error" role="alert">
      {{ error }}
    </p>

    <div class="form-grid">
      <label class="field field-wide">
        <span>Equipamento *</span>

        <input v-model="form.name" maxlength="200" required />
      </label>

      <div class="field">
        <span>Obra *</span>

        <SearchableSelect
          v-model="form.projectContextId"
          :options="contextOptions"
          :clearable="false"
          required
          label="Obra"
          placeholder="Buscar por código ou nome"
          empty-label="Selecione"
          test-id="project-context-select"
        />
      </div>

      <div class="field">
        <span>Origem</span>

        <SearchableSelect
          v-model="form.origin"
          :options="originSelectOptions"
          :clearable="false"
          :sorted="false"
          label="Origem"
          placeholder="Selecione a origem"
          empty-label="Selecione"
          test-id="origin-select"
        />
      </div>

      <div class="field">
        <div class="field-label-row">
          <span>Localização EAP</span>
          <Button
            v-if="auth.can('catalogs:manage')"
            type="button"
            class="eap-manage-button"
            data-testid="edit-eaps"
            variant="ghost"
            @click="showEapAdmin = true"
          >
            <Pencil :size="12" /> Editar EAPs
          </Button>
        </div>
        <SearchableSelect
          v-model="form.eapNodeId"
          :options="eapOptions"
          label="Localização EAP"
          placeholder="Buscar por código ou nome"
          empty-label="Não informada"
          test-id="eap-node-select"
        />
      </div>

      <div class="field">
        <span>Disciplina</span>
        <SearchableSelect
          v-model="form.disciplineId"
          :options="disciplineOptions"
          label="Disciplina"
          placeholder="Buscar disciplina"
          empty-label="Não informada"
        />
      </div>

      <!-- WORK PACKAGES -->
      <div class="field field-wide work-package-field">
        <div class="wp-header">
          <span class="wp-title"> Work Packages </span>

          <span v-if="form.workPackageIds.length" class="wp-count">
            {{ form.workPackageIds.length }}
            {{ form.workPackageIds.length === 1 ? "selecionado" : "selecionados" }}
          </span>
        </div>
        <SearchableMultiSelect
          v-model="form.workPackageIds"
          :options="workPackageOptions"
          label="Work Packages"
          placeholder="Buscar por código, nome ou descrição"
        />
      </div>

      <label class="field">
        <span>Startup</span>

        <input v-model="form.startupAt" type="date" />
      </label>

      <div class="field">
        <div class="field-label-row">
          <span>Criticidade</span>
          <Button
            v-if="auth.can('catalogs:manage')"
            type="button"
            class="eap-manage-button"
            data-testid="edit-criticalities"
            variant="ghost"
            @click="showCriticalityAdmin = true"
          >
            <Pencil :size="12" /> Editar etiquetas
          </Button>
        </div>
        <SearchableSelect
          v-model="form.criticalityLabelId"
          :options="criticalityOptions"
          label="Criticidade"
          placeholder="Buscar criticidade"
          empty-label="Não informada"
          test-id="criticality-select"
        />
      </div>

      <label class="field">
        <span>CAPEX estimado</span>

        <CurrencyInput
          v-model="form.capexEstimated"
          label="CAPEX estimado"
          test-id="capex-input"
        />
      </label>

      <div class="field">
        <span>Responsável</span>
        <SearchableSelect
          v-model="form.responsibleUserId"
          :options="responsibleOptions"
          label="Responsável"
          placeholder="Buscar por nome ou e-mail"
          empty-label="Não atribuído"
          test-id="responsible-select"
        />
      </div>

      <label class="field">
        <span>Valor total do projeto</span>

        <CurrencyInput
          v-model="form.projectTotalValue"
          label="Valor total do projeto"
          test-id="project-total-input"
        />
      </label>

      <label class="field">
        <span>Entrega contratual · de</span>

        <input v-model="form.contractualDeliveryStart" type="date" />
      </label>

      <label class="field">
        <span>Entrega contratual · até</span>

        <input v-model="form.contractualDeliveryEnd" type="date" />
      </label>

      <p v-if="equipment" class="stage-note field-wide">
        A etapa atual é alterada pelo fluxo do processo, na aba Processo.
      </p>
    </div>

    <div class="form-actions">
      <Button variant="outline" @click="emit('cancel')">
        Cancelar
      </Button>

      <Button type="submit" variant="default" :loading="saving">
        {{ saving ? "Salvando..." : "Salvar equipamento" }}
      </Button>
    </div>
  </form>

  <AppModal :open="showEapAdmin" title="Editar Árvore EAP" @close="showEapAdmin = false">
    <EapTreeAdmin @changed="eapCatalogChanged" />
  </AppModal>
  <AppModal :open="showCriticalityAdmin" title="Editar criticidades" @close="showCriticalityAdmin = false">
    <CatalogAdmin
      path="/criticality-labels"
      label="Criticidades"
      :has-code="false"
      :has-color="true"
      @changed="loadCriticalityLabels"
    />
  </AppModal>
</template>

<style scoped>
.form-loading {
  display: flex;
  min-height: 180px;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: #68778c;
}

.equipment-form {
  display: grid;
  gap: 18px;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.field-wide {
  grid-column: 1 / -1;
}

.field > span,
.field-label-row > span {
  color: #56657a;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.03em;
  line-height: 20px;
  text-transform: uppercase;
}
.field-label-row { display: flex; min-height: 20px; align-items: center; justify-content: space-between; gap: 8px; }
.equipment-form :deep(.searchable-select__control) { border-radius: 9px; }

.stage-note {
  margin: 0;
  color: #8b96a5;
  font-size: 11px;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 9px;
  padding-top: 4px;
}

/* =========================================================
   WORK PACKAGES
   ========================================================= */

.work-package-field {
  min-width: 0;
}

.wp-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 7px;
}

.wp-title {
  color: inherit;
}

.wp-count {
  display: inline-flex;
  align-items: center;
  min-height: 20px;
  padding: 2px 8px;

  border: 1px solid #d9e0ec;
  border-radius: 999px;

  background: #f5f7fb;
  color: #68758c;

  font-size: 10px;
  font-weight: 600;
  white-space: nowrap;
}

/* Responsividade */

@media (max-width: 620px) {
  .form-grid {
    grid-template-columns: 1fr;
  }

  .field-wide {
    grid-column: auto;
  }

  .wp-header {
    align-items: flex-start;
  }

}
</style>
