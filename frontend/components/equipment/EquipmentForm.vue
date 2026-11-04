<script setup lang="ts">
import {
  mdiAccount,
  mdiAlertCircleOutline,
  mdiEarth,
  mdiContentSaveOutline,
  mdiMapMarker,
  mdiOfficeBuilding,
  mdiPackageVariant,
  mdiPencilOutline,
  mdiTag,
} from "@mdi/js";
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { VBtn } from "vuetify/components";
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
  dirty: [dirty: boolean];
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
let initialSnapshot = JSON.stringify(form);

watch(
  form,
  () => emit("dirty", JSON.stringify(form) !== initialSnapshot),
  { deep: true },
);

function protectDraft(event: BeforeUnloadEvent): void {
  if (JSON.stringify(form) === initialSnapshot) return;
  event.preventDefault();
  event.returnValue = "";
}

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
    await nextTick();
    initialSnapshot = JSON.stringify(form);
    emit("dirty", false);
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
  if (props.equipment) payload.expectedUpdatedAt = props.equipment.updatedAt;

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

onMounted(() => {
  window.addEventListener("beforeunload", protectDraft);
  void loadCatalogs();
});
onBeforeUnmount(() => window.removeEventListener("beforeunload", protectDraft));
</script>

<template>
  <div v-if="loading" class="form-loading" role="status">
    <span class="spinner" />
    Carregando catálogos...
  </div>

  <form v-else class="equipment-form" @submit.prevent="submit">
    <VAlert v-if="error" type="error" role="alert">
      {{ error }}
    </VAlert>

    <div class="form-sections">
      <section class="form-section" aria-labelledby="equipment-identification-title">
        <div class="section-heading">
          <span>Cadastro</span>
          <h3 id="equipment-identification-title">Identificação</h3>
        </div>

        <div class="form-grid form-grid--three">
          <div class="field field-span-3">
        <VTextField
          v-model="form.name"
          label="Equipamento *"
          maxlength="200"
          required
        />
          </div>

          <div class="field field-span-2">
            <SearchableSelect
              v-model="form.projectContextId"
              :options="contextOptions"
              :clearable="false"
              required
              label="Obra *"
              :icon="mdiOfficeBuilding"
              placeholder="Buscar por código ou nome"
              empty-label="Selecione"
              test-id="project-context-select"
            />
          </div>

          <div class="field">
            <SearchableSelect
              v-model="form.origin"
              :options="originSelectOptions"
              :clearable="false"
              :sorted="false"
              label="Origem"
              :icon="mdiEarth"
              placeholder="Selecione a origem"
              empty-label="Selecione"
              test-id="origin-select"
            />
          </div>
        </div>
      </section>

      <section class="form-section" aria-labelledby="equipment-classification-title">
        <div class="section-heading">
          <span>Organização</span>
          <h3 id="equipment-classification-title">Classificação e responsabilidade</h3>
        </div>

        <div class="form-grid form-grid--three">
          <div class="field field-with-action">
          <VBtn
            v-if="auth.can('catalogs:manage')"
            class="field-action"
            type="button"
            data-testid="edit-eaps"
            variant="tonal"
            color="secondary"
            size="x-small"
            density="compact"
            height="24"
            rounded="lg"
            slim
            :prepend-icon="mdiPencilOutline"
            @click="showEapAdmin = true"
          >
            Editar EAPs
          </VBtn>
            <SearchableSelect
              v-model="form.eapNodeId"
              :options="eapOptions"
              label="Localização EAP"
              :icon="mdiMapMarker"
              placeholder="Buscar por código ou nome"
              empty-label="Não informada"
              test-id="eap-node-select"
            />
          </div>

          <div class="field">
            <SearchableSelect
              v-model="form.disciplineId"
              :options="disciplineOptions"
              label="Disciplina"
              :icon="mdiTag"
              placeholder="Buscar disciplina"
              empty-label="Não informada"
            />
          </div>

          <div class="field field-with-action">
          <VBtn
            v-if="auth.can('catalogs:manage')"
            class="field-action"
            type="button"
            data-testid="edit-criticalities"
            variant="tonal"
            color="secondary"
            size="x-small"
            density="compact"
            height="24"
            rounded="lg"
            slim
            :prepend-icon="mdiPencilOutline"
            @click="showCriticalityAdmin = true"
          >
            Editar etiquetas
          </VBtn>
            <SearchableSelect
              v-model="form.criticalityLabelId"
              :options="criticalityOptions"
              label="Criticidade"
              :icon="mdiAlertCircleOutline"
              placeholder="Buscar criticidade"
              empty-label="Não informada"
              test-id="criticality-select"
            />
          </div>

          <div class="field field-span-2 work-package-field">
            <SearchableMultiSelect
              v-model="form.workPackageIds"
              :options="workPackageOptions"
              label="Work Packages"
              :icon="mdiPackageVariant"
              placeholder="Buscar por código, nome ou descrição"
            />
          </div>

          <div class="field">
            <SearchableSelect
              v-model="form.responsibleUserId"
              :options="responsibleOptions"
              label="Responsável"
              :icon="mdiAccount"
              placeholder="Buscar por nome ou e-mail"
              empty-label="Não atribuído"
              test-id="responsible-select"
            />
          </div>
        </div>
      </section>

      <section class="form-section" aria-labelledby="equipment-planning-title">
        <div class="section-heading">
          <span>Prazos e orçamento</span>
          <h3 id="equipment-planning-title">Planejamento</h3>
        </div>

        <div class="form-grid form-grid--three">
          <div class="field">
            <VTextField v-model="form.startupAt" label="Startup" type="date" />
          </div>
          <div class="field">
            <CurrencyInput
              v-model="form.capexEstimated"
              label="CAPEX estimado"
              test-id="capex-input"
            />
          </div>
          <div class="field">
            <CurrencyInput
              v-model="form.projectTotalValue"
              label="Valor total do projeto"
              test-id="project-total-input"
            />
          </div>
          <div class="field">
            <VTextField
              v-model="form.contractualDeliveryStart"
              label="Entrega contratual · início"
              type="date"
            />
          </div>
          <div class="field">
            <VTextField
              v-model="form.contractualDeliveryEnd"
              label="Entrega contratual · fim"
              type="date"
            />
          </div>

          <p v-if="equipment" class="stage-note">
            A etapa atual é alterada pelo fluxo do processo, na aba Processo.
          </p>
        </div>
      </section>
    </div>

    <div class="form-actions">
      <VBtn type="button" variant="text" color="secondary" @click="emit('cancel')">
        Cancelar
      </VBtn>

      <VBtn
        type="submit"
        variant="flat"
        color="primary"
        :prepend-icon="mdiContentSaveOutline"
        :loading="saving"
        :disabled="saving"
      >
        {{ saving ? "Salvando..." : "Salvar equipamento" }}
      </VBtn>
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
  gap: 14px;
}

.form-sections {
  display: grid;
  gap: 16px;
}

.form-section {
  min-width: 0;
  padding-bottom: 16px;
  border-bottom: 1px solid #e9edf3;
}

.form-section:last-child {
  padding-bottom: 0;
  border-bottom: 0;
}

.section-heading {
  display: flex;
  align-items: baseline;
  gap: 9px;
  margin-bottom: 11px;
}

.section-heading > span {
  color: #1f5aa9;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.section-heading h3 {
  margin: 0;
  color: #263a59;
  font-size: 13px;
  font-weight: 750;
  letter-spacing: -0.01em;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.form-grid--three {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.field-span-3 {
  grid-column: 1 / -1;
}

.field-span-2 {
  grid-column: span 2;
}

.field-with-action {
  position: relative;
  min-width: 0;
}

.field-action {
  position: absolute;
  z-index: 2;
  top: -11px;
  right: 10px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 3px;
  background: #f5f8fd;
  box-shadow: 0 0 0 3px #fff;
  font-size: 11px;
  transition: background-color 160ms ease, border-color 160ms ease, box-shadow 160ms ease, color 160ms ease;
}

.field-action:hover {
  border-color: rgba(31, 90, 169, 0.3);
  background: #eaf1fb;
  box-shadow: 0 0 0 3px #fff, 0 2px 7px rgba(31, 58, 92, 0.13);
  color: #184a8a;
}

.field-action :deep(.v-icon) {
  font-size: 14px;
}

.field-action :deep(.v-btn__prepend),
.field-action :deep(.v-btn__content) {
  display: inline-flex;
  align-items: center;
  line-height: 1;
}

.field-action :deep(.v-btn__prepend) {
  margin-inline: 0 2px;
}

.stage-note {
  align-self: center;
  margin: 0;
  padding: 0 8px;
  color: #8b96a5;
  font-size: 11px;
  line-height: 1.45;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 9px;
  padding-top: 13px;
  border-top: 1px solid #e9edf3;
}

/* =========================================================
   WORK PACKAGES
   ========================================================= */

.work-package-field {
  min-width: 0;
}

@media (max-width: 800px) {
  .form-grid--three {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .field-span-3 {
    grid-column: 1 / -1;
  }
}

@media (max-width: 620px) {
  .form-grid,
  .form-grid--three {
    grid-template-columns: 1fr;
  }

  .field-span-2,
  .field-span-3 {
    grid-column: auto;
  }

  .section-heading {
    display: grid;
    gap: 2px;
  }

  .stage-note {
    padding: 2px 0;
  }
}
</style>
