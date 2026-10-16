import { defineStore } from "pinia";
import type { ModuleContextDefaults } from "~/types/api";
import type { CatalogItem, CatalogList, Equipment, EquipmentList, Unit } from "~/types/equipment";
import { compatibleEquipment } from "~/utils/equipmentFilters";
import { collectAllPages } from "~/utils/pagination";

export interface ModuleContextQuery {
  unit?: string;
  project?: string;
  equipment?: string;
}

/**
 * Contexto global do módulo: Unidade, Obra e Equipamento formam um filtro dependente.
 * As unidades vêm da API já restritas ao que o usuário pode ver.
 */
export const useModuleContextStore = defineStore("moduleContext", () => {
  const units = ref<Unit[]>([]);
  const projectContexts = ref<CatalogItem[]>([]);
  const equipmentOptions = ref<Equipment[]>([]);
  const selectedUnit = ref("");
  const selectedProjectContext = ref("");
  const selectedEquipment = ref("");
  const loading = ref(false);
  const error = ref("");
  const loaded = ref(false);
  /** Carregando opções dependentes (obras/equipamentos) após trocar o filtro. */
  const optionsLoading = ref(false);
  let optionsVersion = 0;

  const selectedUnitLabel = computed(() => {
    const unit = units.value.find((item) => item.id === selectedUnit.value);
    return unit?.name ?? "Todas as unidades";
  });

  function compatibleUnit(unitId: string): string {
    return units.value.some((item) => item.id === unitId) ? unitId : "";
  }

  /** Filtros que vão para a API; chaves omitidas quando não há seleção. */
  const apiQuery = computed<Record<string, string>>(() => {
    const query: Record<string, string> = {};
    if (selectedUnit.value) query.unit_id = selectedUnit.value;
    if (selectedProjectContext.value) query.project_context_id = selectedProjectContext.value;
    if (selectedEquipment.value) query.equipment_id = selectedEquipment.value;
    return query;
  });

  async function loadProjectContexts(): Promise<void> {
    projectContexts.value = [];
    if (!selectedUnit.value) {
      selectedProjectContext.value = "";
      return;
    }
    const version = optionsVersion;
    const items = (
      await useApi().get<CatalogList<CatalogItem>>(
        `/units/${selectedUnit.value}/project-contexts`,
      )
    ).items;
    if (version !== optionsVersion) return;
    projectContexts.value = items;
    if (!projectContexts.value.some((item) => item.id === selectedProjectContext.value)) {
      selectedProjectContext.value = "";
    }
  }

  async function loadEquipmentOptions(): Promise<void> {
    equipmentOptions.value = [];
    if (!selectedUnit.value) {
      selectedEquipment.value = "";
      return;
    }
    const query: Record<string, string | number> = {
      unit_id: selectedUnit.value,
      pageSize: 100,
      sortBy: "name",
    };
    if (selectedProjectContext.value) {
      query.project_context_id = selectedProjectContext.value;
    }
    const version = optionsVersion;
    const items = await collectAllPages((page) =>
      useApi().get<EquipmentList>("/equipments", { ...query, page }),
    );
    if (version !== optionsVersion) return;
    equipmentOptions.value = items;
    selectedEquipment.value = compatibleEquipment(equipmentOptions.value, selectedEquipment.value);
  }

  /** Carrega uma vez por sessão. URL explícita vence o contexto inicial da API. */
  async function initialize(query: ModuleContextQuery = {}): Promise<void> {
    if (loaded.value) {
      await applyFromQuery(query);
      return;
    }
    loading.value = true;
    error.value = "";
    try {
      const api = useApi();
      const [unitList, defaults] = await Promise.all([
        api.get<CatalogList<Unit>>("/units"),
        api.get<ModuleContextDefaults>("/module-context/defaults").catch(() => null),
      ]);
      units.value = unitList.items;
      const hasExplicitFilter = Object.values(query).some((value) => value !== undefined);
      if (hasExplicitFilter) {
        selectedUnit.value = compatibleUnit(query.unit ?? "");
        selectedProjectContext.value = query.project ?? "";
        selectedEquipment.value = query.equipment ?? "";
      } else if (!defaults || defaults.firstAccess) {
        selectedUnit.value = "";
        selectedProjectContext.value = "";
        selectedEquipment.value = "";
      } else {
        selectedUnit.value = compatibleUnit(defaults.unitId ?? "");
        selectedProjectContext.value = defaults.projectContextId ?? "";
        selectedEquipment.value = "";
      }
      await loadProjectContexts();
      await loadEquipmentOptions();
      loaded.value = true;
    } catch (caught) {
      error.value =
        caught instanceof Error ? caught.message : "Não foi possível carregar as unidades.";
    } finally {
      loading.value = false;
    }
  }

  /** Reaplica filtros de uma URL compartilhada sem recarregar as unidades. */
  async function applyFromQuery(query: ModuleContextQuery): Promise<void> {
    const hasExplicitFilter = Object.values(query).some((value) => value !== undefined);
    if (!hasExplicitFilter) return;

    const unitExplicit = query.unit !== undefined;
    const projectExplicit = query.project !== undefined;
    const equipmentExplicit = query.equipment !== undefined;
    const nextUnit = unitExplicit ? compatibleUnit(query.unit ?? "") : selectedUnit.value;
    const unitChanged = nextUnit !== selectedUnit.value;
    const previousProject = selectedProjectContext.value;
    selectedUnit.value = nextUnit;
    if (projectExplicit) selectedProjectContext.value = query.project ?? "";
    else if (unitChanged) selectedProjectContext.value = "";
    if (equipmentExplicit) selectedEquipment.value = query.equipment ?? "";
    else if (unitChanged) selectedEquipment.value = "";
    if (unitChanged || (selectedUnit.value && projectContexts.value.length === 0)) {
      await loadProjectContexts();
    } else if (!projectContexts.value.some((item) => item.id === selectedProjectContext.value)) {
      selectedProjectContext.value = "";
    }
    if (
      unitChanged ||
      previousProject !== selectedProjectContext.value ||
      equipmentOptions.value.length === 0
    ) {
      await loadEquipmentOptions();
    } else {
      selectedEquipment.value = compatibleEquipment(equipmentOptions.value, selectedEquipment.value);
    }
  }

  /** Trocar a unidade sempre descarta um equipamento incompatível. */
  async function setUnit(unitId: string): Promise<void> {
    selectedUnit.value = unitId;
    selectedProjectContext.value = "";
    selectedEquipment.value = "";
    error.value = "";
    const version = ++optionsVersion;
    optionsLoading.value = true;
    try {
      await loadProjectContexts();
      if (version !== optionsVersion) return;
      await loadEquipmentOptions();
    } catch (caught) {
      if (version !== optionsVersion) return;
      error.value =
        caught instanceof Error ? caught.message : "Não foi possível carregar os equipamentos.";
    } finally {
      if (version === optionsVersion) optionsLoading.value = false;
    }
  }

  async function setProjectContext(projectContextId: string): Promise<void> {
    selectedProjectContext.value = projectContexts.value.some(
      (item) => item.id === projectContextId,
    )
      ? projectContextId
      : "";
    selectedEquipment.value = "";
    error.value = "";
    const version = ++optionsVersion;
    optionsLoading.value = true;
    try {
      await loadEquipmentOptions();
    } catch (caught) {
      if (version !== optionsVersion) return;
      error.value =
        caught instanceof Error ? caught.message : "Não foi possível carregar os equipamentos.";
    } finally {
      if (version === optionsVersion) optionsLoading.value = false;
    }
  }

  function setEquipment(equipmentId: string): void {
    selectedEquipment.value = compatibleEquipment(equipmentOptions.value, equipmentId);
  }

  return {
    units,
    projectContexts,
    equipmentOptions,
    selectedUnit,
    selectedProjectContext,
    selectedEquipment,
    selectedUnitLabel,
    apiQuery,
    loading,
    optionsLoading,
    error,
    loaded,
    initialize,
    applyFromQuery,
    setUnit,
    setProjectContext,
    setEquipment,
    loadProjectContexts,
    loadEquipmentOptions,
  };
});
