import { defineStore } from "pinia";
import type { CatalogList, Equipment, EquipmentList, Unit } from "~/types/equipment";
import { compatibleEquipment, initialUnit } from "~/utils/equipmentFilters";

/**
 * Contexto global do módulo: Unidade e Equipamento valem para todas as telas.
 * As unidades vêm da API já restritas ao que o usuário pode ver.
 */
export const useModuleContextStore = defineStore("moduleContext", () => {
  const units = ref<Unit[]>([]);
  const equipmentOptions = ref<Equipment[]>([]);
  const selectedUnit = ref("");
  const selectedEquipment = ref("");
  const loading = ref(false);
  const error = ref("");
  const loaded = ref(false);

  const selectedUnitLabel = computed(() => {
    const unit = units.value.find((item) => item.id === selectedUnit.value);
    return unit ? `${unit.code} · ${unit.name}` : "Todas as unidades";
  });

  /** Filtros que vão para a API; chaves omitidas quando não há seleção. */
  const apiQuery = computed<Record<string, string>>(() => {
    const query: Record<string, string> = {};
    if (selectedUnit.value) query.unit_id = selectedUnit.value;
    if (selectedEquipment.value) query.equipment_id = selectedEquipment.value;
    return query;
  });

  async function loadEquipmentOptions(): Promise<void> {
    equipmentOptions.value = [];
    if (!selectedUnit.value) {
      selectedEquipment.value = "";
      return;
    }
    const result = await useApi().get<EquipmentList>("/equipments", {
      unit_id: selectedUnit.value,
      pageSize: 100,
      sortBy: "name",
    });
    equipmentOptions.value = result.items;
    selectedEquipment.value = compatibleEquipment(equipmentOptions.value, selectedEquipment.value);
  }

  /** Carrega as unidades uma vez por sessão e aplica os filtros vindos da URL. */
  async function initialize(query: { unit?: string; equipment?: string } = {}): Promise<void> {
    if (loaded.value) {
      await applyFromQuery(query);
      return;
    }
    loading.value = true;
    error.value = "";
    try {
      units.value = (await useApi().get<CatalogList<Unit>>("/units")).items;
      selectedUnit.value = initialUnit(units.value, query.unit ?? "");
      selectedEquipment.value = query.equipment ?? "";
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
  async function applyFromQuery(query: { unit?: string; equipment?: string }): Promise<void> {
    const nextUnit = initialUnit(units.value, query.unit ?? selectedUnit.value);
    const unitChanged = nextUnit !== selectedUnit.value;
    selectedUnit.value = nextUnit;
    if (query.equipment !== undefined) selectedEquipment.value = query.equipment;
    if (unitChanged || equipmentOptions.value.length === 0) await loadEquipmentOptions();
    else selectedEquipment.value = compatibleEquipment(equipmentOptions.value, selectedEquipment.value);
  }

  /** Trocar a unidade sempre descarta um equipamento incompatível. */
  async function setUnit(unitId: string): Promise<void> {
    selectedUnit.value = unitId;
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
    equipmentOptions,
    selectedUnit,
    selectedEquipment,
    selectedUnitLabel,
    apiQuery,
    loading,
    error,
    loaded,
    initialize,
    applyFromQuery,
    setUnit,
    setEquipment,
    loadEquipmentOptions,
  };
});
