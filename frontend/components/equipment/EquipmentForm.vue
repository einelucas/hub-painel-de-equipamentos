<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import SearchableMultiSelect from "~/components/ui/SearchableMultiSelect.vue";
import SearchableSelect from "~/components/ui/SearchableSelect.vue";
import type {
  CatalogItem,
  CatalogList,
  EapNodeItem,
  Equipment,
  ProjectEapItem,
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

const contexts = ref<CatalogItem[]>([]);
const eapNodes = ref<EapNodeItem[]>([]);
const disciplines = ref<CatalogItem[]>([]);
const workPackages = ref<CatalogItem[]>([]);
const responsibles = ref<Responsible[]>([]);

const loading = ref(true);
const saving = ref(false);
const error = ref("");

const form = reactive({
  name: props.equipment?.name ?? "",
  projectContextId: props.equipment?.projectContext.id ?? "",
  origin: props.equipment?.origin ?? "",
  startupAt: props.equipment?.startupAt ?? "",
  disciplineId: props.equipment?.discipline?.id ?? "",
  eapNodeId: props.equipment?.eapNode?.id ?? "",

  // Relação N:N com pacotes de trabalho.
  workPackageIds: props.equipment?.workPackages.map((item) => item.id) ?? [],

  criticality: props.equipment?.criticality ?? "",
  capexEstimated: props.equipment?.capexEstimated?.toString() ?? "",
  responsibleUserId: props.equipment?.responsibleUser?.id ?? "",
  projectTotalValue: props.equipment?.projectTotalValue?.toString() ?? "",
  contractualDeliveryStart: props.equipment?.contractualDeliveryStart ?? "",
  contractualDeliveryEnd: props.equipment?.contractualDeliveryEnd ?? "",
});

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
  workPackages.value = [];

  if (!form.projectContextId) {
    form.workPackageIds = [];
    return;
  }

  workPackages.value = (
    await api.get<CatalogList<CatalogItem>>("/work-packages", {
      project_context_id: form.projectContextId,
    })
  ).items;

  // Contexto mudou: remove pacotes que não pertencem
  // ao contexto atualmente selecionado.
  form.workPackageIds = form.workPackageIds.filter((id) =>
    workPackages.value.some((item) => item.id === id),
  );
}

async function loadEapNodes(): Promise<void> {
  eapNodes.value = [];

  if (!form.projectContextId) {
    form.eapNodeId = "";
    return;
  }

  const linked = await api.get<CatalogList<ProjectEapItem>>(
    `/project-contexts/${form.projectContextId}/eap-nodes`,
  );
  const candidates = linked.items.length
    ? linked.items.map((item) => item.eapNode)
    : (
        await api.get<CatalogList<EapNodeItem>>("/eap-nodes", {
          active: true,
        })
      ).items;

  eapNodes.value = candidates.filter(
    (item) => item.active && (item.level === "PROCESS" || item.level === "AREA"),
  );
  if (!eapNodes.value.some((item) => item.id === form.eapNodeId)) {
    form.eapNodeId = "";
  }
}

async function loadContextCatalogs(): Promise<void> {
  await Promise.all([loadEapNodes(), loadWorkPackages()]);
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

    await loadContextCatalogs();
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
    criticality: form.criticality || null,
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
  <div v-if="loading" class="form-loading">
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

      <label class="field">
        <span>Contexto *</span>

        <select
          v-model="form.projectContextId"
          required
          @change="loadContextCatalogs"
        >
          <option value="">Selecione</option>

          <option v-for="item in contexts" :key="item.id" :value="item.id">
            {{ item.code ? `${item.code} · ${item.name}` : item.name }}
          </option>
        </select>
      </label>

      <label class="field">
        <span>Origem</span>

        <input v-model="form.origin" maxlength="160" />
      </label>

      <div class="field">
        <span>Localização EAP</span>
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
          :disabled="!form.projectContextId"
          disabled-message="Selecione um contexto para visualizar as WPs disponíveis."
        />
      </div>

      <label class="field">
        <span>Startup</span>

        <input v-model="form.startupAt" type="date" />
      </label>

      <label class="field">
        <span>Criticidade</span>

        <input
          v-model="form.criticality"
          maxlength="40"
          placeholder="Conforme classificação oficial"
        />
      </label>

      <label class="field">
        <span>CAPEX estimado</span>

        <input
          v-model="form.capexEstimated"
          type="number"
          min="0"
          step="0.01"
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

        <input
          v-model="form.projectTotalValue"
          type="number"
          min="0"
          step="0.01"
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
      <button type="button" class="btn" @click="emit('cancel')">
        Cancelar
      </button>

      <button type="submit" class="btn primary" :disabled="saving">
        {{ saving ? "Salvando..." : "Salvar equipamento" }}
      </button>
    </div>
  </form>
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
