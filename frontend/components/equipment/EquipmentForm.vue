<script setup lang="ts">
import type {
  CatalogItem,
  CatalogList,
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

const contexts = ref<CatalogItem[]>([]);
const areas = ref<CatalogItem[]>([]);
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
  areaId: props.equipment?.area?.id ?? "",

  // Relação N:N com pacotes de trabalho.
  workPackageIds: props.equipment?.workPackages.map((item) => item.id) ?? [],

  criticality: props.equipment?.criticality ?? "",
  capexEstimated: props.equipment?.capexEstimated?.toString() ?? "",
  responsibleUserId: props.equipment?.responsibleUser?.id ?? "",
  projectTotalValue: props.equipment?.projectTotalValue?.toString() ?? "",
  contractualDeliveryStart: props.equipment?.contractualDeliveryStart ?? "",
  contractualDeliveryEnd: props.equipment?.contractualDeliveryEnd ?? "",
});

const workPackageSearch = ref("");

const selectedWorkPackages = computed(() =>
  workPackages.value
    .filter((item) => form.workPackageIds.includes(item.id))
    .sort((a, b) => (a.code ?? a.name).localeCompare(b.code ?? b.name)),
);

const filteredWorkPackages = computed(() => {
  const term = workPackageSearch.value.trim().toLowerCase();

  if (!term) {
    return workPackages.value;
  }

  return workPackages.value.filter((item) => {
    const code = item.code?.toLowerCase() ?? "";
    const name = item.name.toLowerCase();

    return code.includes(term) || name.includes(term);
  });
});

function removeWorkPackage(id: string): void {
  form.workPackageIds = form.workPackageIds.filter((item) => item !== id);
}

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

async function loadCatalogs(): Promise<void> {
  loading.value = true;

  try {
    const [contextResult, areaResult, disciplineResult, responsibleResult] =
      await Promise.all([
        api.get<CatalogList<CatalogItem>>(
          `/units/${props.unitId}/project-contexts`,
        ),
        api.get<CatalogList<CatalogItem>>("/areas", {
          unit_id: props.unitId,
        }),
        api.get<CatalogList<CatalogItem>>("/disciplines"),
        api.get<CatalogList<Responsible>>("/responsibles", {
          unit_id: props.unitId,
        }),
      ]);

    contexts.value = contextResult.items;
    areas.value = areaResult.items;
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

    await loadWorkPackages();
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
    areaId: form.areaId || null,
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
          @change="loadWorkPackages"
        >
          <option value="">Selecione</option>

          <option v-for="item in contexts" :key="item.id" :value="item.id">
            {{ item.code }} · {{ item.name }}
          </option>
        </select>
      </label>

      <label class="field">
        <span>Origem</span>

        <input v-model="form.origin" maxlength="160" />
      </label>

      <label class="field">
        <span>Área</span>

        <select v-model="form.areaId">
          <option value="">Não informada</option>

          <option v-for="item in areas" :key="item.id" :value="item.id">
            {{ item.name }}
          </option>
        </select>
      </label>

      <label class="field">
        <span>Disciplina</span>

        <select v-model="form.disciplineId">
          <option value="">Não informada</option>

          <option v-for="item in disciplines" :key="item.id" :value="item.id">
            {{ item.name }}
          </option>
        </select>
      </label>

      <!-- PACOTES DE TRABALHO -->
      <div class="field field-wide work-package-field">
        <div class="wp-header">
          <span class="wp-title"> Pacotes de trabalho </span>

          <span v-if="selectedWorkPackages.length" class="wp-count">
            {{ selectedWorkPackages.length }}
            {{
              selectedWorkPackages.length === 1 ? "selecionado" : "selecionados"
            }}
          </span>
        </div>

        <div
          class="wp-picker"
          :class="{
            'wp-picker-disabled': !form.projectContextId,
          }"
        >
          <!-- Pacotes selecionados -->
          <div v-if="selectedWorkPackages.length" class="wp-selected">
            <span
              v-for="item in selectedWorkPackages"
              :key="item.id"
              class="wp-chip"
            >
              <span class="wp-chip-label">
                {{ item.code ?? item.name }}
              </span>

              <button
                type="button"
                class="wp-chip-remove"
                :aria-label="`Remover ${item.code ?? item.name}`"
                @click="removeWorkPackage(item.id)"
              >
                <svg viewBox="0 0 16 16" aria-hidden="true">
                  <path
                    d="M4 4l8 8M12 4l-8 8"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="1.8"
                    stroke-linecap="round"
                  />
                </svg>
              </button>
            </span>
          </div>

          <div v-else class="wp-no-selection">Nenhum pacote selecionado</div>

          <!-- Pesquisa -->
          <div class="wp-search-wrapper">
            <svg class="wp-search-icon" viewBox="0 0 24 24" aria-hidden="true">
              <circle
                cx="11"
                cy="11"
                r="7"
                fill="none"
                stroke="currentColor"
                stroke-width="1.8"
              />

              <path
                d="M16.2 16.2L21 21"
                fill="none"
                stroke="currentColor"
                stroke-width="1.8"
                stroke-linecap="round"
              />
            </svg>

            <input
              v-model="workPackageSearch"
              type="search"
              class="wp-search"
              placeholder="Buscar por código ou nome..."
              :disabled="!form.projectContextId"
            />
          </div>

          <!-- Opções -->
          <div class="wp-options">
            <div v-if="!form.projectContextId" class="wp-message">
              Selecione um contexto para visualizar os pacotes disponíveis.
            </div>

            <div v-else-if="!filteredWorkPackages.length" class="wp-message">
              Nenhum pacote encontrado.
            </div>

            <label
              v-for="item in filteredWorkPackages"
              v-else
              :key="item.id"
              class="wp-option"
              :class="{
                'wp-option-selected': form.workPackageIds.includes(item.id),
              }"
            >
              <input
                v-model="form.workPackageIds"
                class="wp-checkbox-input"
                type="checkbox"
                :value="item.id"
              />

              <span class="wp-checkbox" aria-hidden="true">
                <svg viewBox="0 0 16 16">
                  <path
                    d="M3.2 8.2l3 3 6.5-6.4"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="2"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                  />
                </svg>
              </span>

              <span class="wp-option-content">
                <strong class="wp-option-code">
                  {{ item.code ?? item.name }}
                </strong>

                <span
                  v-if="
                    item.code &&
                    item.name.trim().toLowerCase() !==
                      item.code.trim().toLowerCase()
                  "
                  class="wp-option-name"
                >
                  {{ item.name }}
                </span>
              </span>
            </label>
          </div>
        </div>
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

      <label class="field">
        <span>Responsável</span>

        <select
          v-model="form.responsibleUserId"
          data-testid="responsible-select"
        >
          <option value="">Não atribuído</option>

          <option v-for="item in responsibles" :key="item.id" :value="item.id">
            {{ item.name }}
          </option>
        </select>
      </label>

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

.wp-picker {
  overflow: hidden;

  border: 1px solid #d6ddea;
  border-radius: 9px;

  background: #fff;

  transition:
    border-color 0.15s ease,
    box-shadow 0.15s ease;
}

.wp-picker:focus-within {
  border-color: #8797bd;
  box-shadow: 0 0 0 3px rgb(67 83 130 / 7%);
}

.wp-picker-disabled {
  background: #fafbfc;
}

/* Selecionados */

.wp-selected {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;

  padding: 9px 10px 3px;
}

.wp-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;

  max-width: 100%;
  min-height: 25px;
  padding: 3px 5px 3px 9px;

  border: 1px solid #d7dfef;
  border-radius: 6px;

  background: #eef2fa;
  color: #3b4a70;

  font-size: 11px;
  font-weight: 650;
}

.wp-chip-label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.wp-chip-remove {
  display: grid;
  width: 18px;
  height: 18px;
  flex: 0 0 18px;
  place-items: center;

  padding: 0;

  border: 0;
  border-radius: 4px;

  background: transparent;
  color: #7886a0;

  cursor: pointer;
}

.wp-chip-remove svg {
  width: 11px;
  height: 11px;
}

.wp-chip-remove:hover {
  background: #dce4f4;
  color: #34466f;
}

.wp-no-selection {
  padding: 9px 10px 3px;

  color: #929caf;
  font-size: 11px;
}

/* Busca */

.wp-search-wrapper {
  position: relative;

  padding: 7px 9px 8px;
}

.wp-search-icon {
  position: absolute;
  top: 50%;
  left: 21px;

  width: 15px;
  height: 15px;

  color: #909bae;

  pointer-events: none;

  transform: translateY(-50%);
}

.wp-search {
  box-sizing: border-box;
  width: 100%;
  height: 35px;

  padding: 0 11px 0 34px;

  border: 1px solid #d9dfea;
  border-radius: 6px;

  background: #fff;
  color: #3c485f;

  font: inherit;
  font-size: 12px;

  outline: none;

  transition:
    border-color 0.15s ease,
    box-shadow 0.15s ease;
}

.wp-search::placeholder {
  color: #a0a9ba;
}

.wp-search:focus {
  border-color: #8797bd;
  box-shadow: 0 0 0 3px rgb(67 83 130 / 6%);
}

.wp-search:disabled {
  background: #f6f7f9;
  color: #9ca5b4;
  cursor: not-allowed;
}

/* Lista */

.wp-options {
  max-height: 170px;
  overflow-y: auto;

  padding: 4px 6px 6px;

  border-top: 1px solid #edf0f5;
  background: #fbfcfe;

  scrollbar-width: thin;
  scrollbar-color: #bec5d0 transparent;
}

.wp-options::-webkit-scrollbar {
  width: 6px;
}

.wp-options::-webkit-scrollbar-track {
  background: transparent;
}

.wp-options::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: #bec5d0;
}

.wp-message {
  display: flex;
  min-height: 56px;
  align-items: center;
  justify-content: center;

  padding: 10px;

  color: #909bad;

  font-size: 11px;
  text-align: center;
}

/* Item */

.wp-option {
  position: relative;

  display: flex;
  min-height: 38px;
  align-items: center;
  gap: 9px;

  padding: 5px 8px;

  border-radius: 6px;

  cursor: pointer;
  user-select: none;

  transition:
    background-color 0.15s ease,
    box-shadow 0.15s ease;
}

.wp-option + .wp-option {
  margin-top: 1px;
}

.wp-option:hover {
  background: #f0f3f8;
}

.wp-option-selected {
  background: #eef2fa;
}

.wp-option-selected:hover {
  background: #e8edf8;
}

/*
 * O checkbox real fica invisível.
 * Isso impede que os estilos globais de input
 * criem os quadrados gigantes da interface anterior.
 */
.wp-checkbox-input {
  position: absolute !important;

  width: 1px !important;
  height: 1px !important;

  margin: -1px !important;
  padding: 0 !important;

  overflow: hidden;

  clip: rect(0, 0, 0, 0);
  clip-path: inset(50%);

  border: 0 !important;

  opacity: 0;
  white-space: nowrap;
}

.wp-checkbox {
  display: grid;
  width: 16px;
  height: 16px;
  flex: 0 0 16px;
  place-items: center;

  box-sizing: border-box;

  border: 1.5px solid #aeb7c7;
  border-radius: 4px;

  background: #fff;
  color: transparent;

  transition:
    background-color 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease;
}

.wp-checkbox svg {
  width: 11px;
  height: 11px;
}

.wp-checkbox-input:checked + .wp-checkbox {
  border-color: #435487;
  background: #435487;
  color: #fff;
}

.wp-checkbox-input:focus-visible + .wp-checkbox {
  box-shadow: 0 0 0 3px rgb(67 84 135 / 15%);
}

.wp-option-content {
  display: flex;
  min-width: 0;
  flex: 1;
  align-items: center;
  gap: 8px;
}

.wp-option-code {
  flex: 0 0 auto;

  color: #3a465e;

  font-size: 11.5px;
  font-weight: 650;
}

.wp-option-name {
  overflow: hidden;
  min-width: 0;
  flex: 1;

  color: #7e899c;

  font-size: 11.5px;

  text-overflow: ellipsis;
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

  .wp-option-content {
    align-items: flex-start;
    flex-direction: column;
    gap: 1px;
  }

  .wp-options {
    max-height: 190px;
  }
}
</style>
