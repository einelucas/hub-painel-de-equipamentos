import { defineStore } from "pinia";
import type { CatalogItem, CatalogList, Equipment, EquipmentList, Unit } from "~/types/equipment";
import { compatibleEquipment, initialUnit } from "~/utils/equipmentFilters";

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

  const selectedUnitLabel = computed(() => {
    const unit = units.value.find((item) => item.id === selectedUnit.value);
    return unit?.name ?? "Todas as unidades";
  });

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
    projectContexts.value = (
      await useApi().get<CatalogList<CatalogItem>>(
        `/units/${selectedUnit.value}/project-contexts`,
      )
    ).items;
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
    const result = await useApi().get<EquipmentList>("/equipments", query);
    equipmentOptions.value = result.items;
    selectedEquipment.value = compatibleEquipment(equipmentOptions.value, selectedEquipment.value);
  }

  /** Carrega as unidades uma vez por sessão e aplica os filtros vindos da URL. */
  async function initialize(
    query: { unit?: string; project?: string; equipment?: string } = {},
  ): Promise<void> {
    if (loaded.value) {
      await applyFromQuery(query);
      return;
    }
    loading.value = true;
    error.value = "";
    try {
      units.value = (await useApi().get<CatalogList<Unit>>("/units")).items;
      selectedUnit.value = initialUnit(units.value, query.unit ?? "");
      selectedProjectContext.value = query.project ?? "";
      selectedEquipment.value = query.equipment ?? "";
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
  async function applyFromQuery(query: {
    unit?: string;
    project?: string;
    equipment?: string;
  }): Promise<void> {
    const nextUnit = initialUnit(units.value, query.unit ?? selectedUnit.value);
    const unitChanged = nextUnit !== selectedUnit.value;
    const previousProject = selectedProjectContext.value;
    selectedUnit.value = nextUnit;
    if (unitChanged) selectedProjectContext.value = query.project ?? "";
    else selectedProjectContext.value = query.project ?? "";
    if (query.equipment !== undefined) selectedEquipment.value = query.equipment;
    if (unitChanged || (selectedUnit.value && projectContexts.value.length === 0)) {
      await loadProjectContexts();
    } else if (!projectContexts.value.some((item) => item.id === selectedProjectContext.value)) {
      selectedProjectContext.value = "";
    }
    if (
      unitChanged ||
      previousProject !== selectedProjectContext.value ||
      equipmentOptions.value.length === 0
    ) await loadEquipmentOptions();
    else selectedEquipment.value = compatibleEquipment(equipmentOptions.value, selectedEquipment.value);
  }

  /** Trocar a unidade sempre descarta um equipamento incompatível. */
  async function setUnit(unitId: string): Promise<void> {
    selectedUnit.value = unitId;
    selectedProjectContext.value = "";
    selectedEquipment.value = "";
    error.value = "";
    try {
      await loadProjectContexts();
      await loadEquipmentOptions();
    } catch (caught) {
      error.value =
        caught instanceof Error ? caught.message : "Não foi possível carregar os equipamentos.";
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
    try {
      await loadEquipmentOptions();
    } catch (caught) {
      error.value =
        caught instanceof Error ? caught.message : "Não foi possível carregar os equipamentos.";
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
