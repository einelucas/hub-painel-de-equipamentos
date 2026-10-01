import { computed, reactive } from "vue";
import type { LocationQuery } from "vue-router";
import { EQUIPMENT_STAGES } from "~/utils/stages";

/** Filtros globais do Dashboard (Área AND Disciplina AND Fase). `null` = sem restrição. */
export interface DashboardFilterState {
  areaId: string | null;
  disciplineId: string | null;
  stage: number | null;
}

type QueryValue = LocationQuery[string] | undefined;

function queryString(value: QueryValue): string | null {
  return typeof value === "string" && value !== "" ? value : null;
}

function queryStage(value: QueryValue): number | null {
  const raw = queryString(value);
  if (raw === null || !/^\d+$/.test(raw)) return null;
  const stage = Number(raw);
  return stage < EQUIPMENT_STAGES.length ? stage : null;
}

export function useDashboardFilters() {
  const filters = reactive<DashboardFilterState>({ areaId: null, disciplineId: null, stage: null });

  const hasActive = computed(
    () => filters.areaId !== null || filters.disciplineId !== null || filters.stage !== null,
  );

  /** Parâmetros de `/dashboard/summary`; filtros sem seleção são omitidos. */
  const apiQuery = computed<Record<string, string>>(() => {
    const query: Record<string, string> = {};
    if (filters.areaId) query.area_id = filters.areaId;
    if (filters.disciplineId) query.discipline_id = filters.disciplineId;
    if (filters.stage !== null) query.stage = String(filters.stage);
    return query;
  });

  function readRouteQuery(query: LocationQuery): void {
    filters.areaId = queryString(query.area);
    filters.disciplineId = queryString(query.discipline);
    filters.stage = queryStage(query.stage);
  }

  function writeRouteQuery(query: Record<string, string>): void {
    if (filters.areaId) query.area = filters.areaId;
    else delete query.area;
    if (filters.disciplineId) query.discipline = filters.disciplineId;
    else delete query.discipline;
    if (filters.stage !== null) query.stage = String(filters.stage);
    else delete query.stage;
  }

  function clear(): void {
    filters.areaId = null;
    filters.disciplineId = null;
    filters.stage = null;
  }

  return { filters, hasActive, apiQuery, readRouteQuery, writeRouteQuery, clear };
}
