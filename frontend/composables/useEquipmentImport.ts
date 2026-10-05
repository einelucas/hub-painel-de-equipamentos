import { computed, reactive, ref } from "vue";
import { ApiError } from "~/services/api/error";
import type { CatalogItem, CatalogList, Responsible, Unit } from "~/types/equipment";
import type {
  ImportApplyResult,
  ImportBatch,
  ImportMapping,
  ImportOption,
  ImportPlan,
  ImportProfile,
  MappingSection,
} from "~/types/imports";

/**
 * Estado do wizard "Importar equipamentos" enquanto o modal está aberto.
 * O frontend só envia o arquivo e as escolhas do usuário: parsing, staging,
 * mapping, plan, apply e reconciliação acontecem no backend (motor monday_import).
 */
export type ImportStep = "source" | "analysis" | "mapping" | "plan" | "result";
export const IMPORT_STEPS: { key: ImportStep; label: string }[] = [
  { key: "source", label: "Obra e arquivo" },
  { key: "analysis", label: "Análise" },
  { key: "mapping", label: "Mapeamento" },
  { key: "plan", label: "Plano" },
  { key: "result", label: "Resultado" },
];
export const MAPPING_SECTIONS: { key: MappingSection; label: string }[] = [
  { key: "responsibles", label: "Responsáveis" },
  { key: "areas", label: "Áreas" },
  { key: "disciplines", label: "Disciplinas" },
  { key: "workPackages", label: "Work Packages" },
];

const BASE = "/imports/monday";

export function isXlsx(fileName: string): boolean {
  return fileName.toLowerCase().endsWith(".xlsx");
}

function emptyMapping(): ImportMapping {
  return { responsibles: {}, areas: {}, disciplines: {}, workPackages: {} };
}

function message(caught: unknown, fallback: string): string {
  return caught instanceof Error && caught.message ? caught.message : fallback;
}

export function useEquipmentImport() {
  const api = useApi();

  const step = ref<ImportStep>("source");
  const units = ref<Unit[]>([]);
  const contexts = ref<CatalogItem[]>([]);
  const profiles = ref<ImportProfile[]>([]);
  const selection = reactive({ unitId: "", contextId: "", profileId: "" });
  const file = ref<File | null>(null);
  const batch = ref<ImportBatch | null>(null);
  const mapping = ref<ImportMapping>(emptyMapping());
  const options = ref<Record<MappingSection, ImportOption[]>>({
    responsibles: [],
    areas: [],
    disciplines: [],
    workPackages: [],
  });
  const plan = ref<ImportPlan | null>(null);
  const result = ref<ImportApplyResult | null>(null);
  const busy = ref(false);
  const error = ref("");
  const stale = ref(false);

  const selectedContext = computed(() => contexts.value.find((item) => item.id === selection.contextId) ?? null);
  const hasProgress = computed(() => batch.value !== null && result.value === null);

  async function loadSetup(preferredUnitId = ""): Promise<void> {
    busy.value = true;
    error.value = "";
    try {
      const [unitList, profileList] = await Promise.all([
        api.get<CatalogList<Unit>>("/units"),
        api.get<CatalogList<ImportProfile>>(`${BASE}/profiles`),
      ]);
      units.value = unitList.items;
      profiles.value = profileList.items;
      if (profiles.value.length === 1) selection.profileId = profiles.value[0]!.profileId;
      if (preferredUnitId && units.value.some((unit) => unit.id === preferredUnitId)) {
        selection.unitId = preferredUnitId;
        await loadContexts();
      }
    } catch (caught) {
      error.value = message(caught, "Não foi possível carregar as opções de importação.");
    } finally {
      busy.value = false;
    }
  }

  /** Só contextos ativos (listagem padrão da API) recebem nova importação. */
  async function loadContexts(): Promise<void> {
    contexts.value = [];
    selection.contextId = "";
    if (!selection.unitId) return;
    contexts.value = (await api.get<CatalogList<CatalogItem>>(`/units/${selection.unitId}/project-contexts`)).items;
    if (contexts.value.length === 1) selection.contextId = contexts.value[0]!.id;
  }

  function selectFile(candidate: File | null): void {
    error.value = "";
    if (candidate && !isXlsx(candidate.name)) {
      file.value = null;
      error.value = "Envie um arquivo .xlsx exportado do Monday.";
      return;
    }
    file.value = candidate;
  }

  async function analyze(): Promise<void> {
    if (!file.value || !selection.contextId || !selection.profileId) return;
    busy.value = true;
    error.value = "";
    try {
      const form = new FormData();
      form.append("projectContextId", selection.contextId);
      form.append("profileId", selection.profileId);
      form.append("file", file.value, file.value.name);
      batch.value = await api.upload<ImportBatch>(`${BASE}/batches`, form, "POST");
      mapping.value = emptyMapping();
      plan.value = null;
      step.value = "analysis";
    } catch (caught) {
      error.value = message(caught, "Não foi possível analisar a planilha.");
    } finally {
      busy.value = false;
    }
  }

  /** Alvos do mapping vêm dos catálogos existentes; nada é criado aqui. */
  async function loadMappingOptions(): Promise<void> {
    busy.value = true;
    error.value = "";
    try {
      const [responsibles, areas, disciplines, workPackages] = await Promise.all([
        api.get<CatalogList<Responsible>>("/responsibles", { unit_id: selection.unitId }),
        api.get<CatalogList<CatalogItem>>("/areas", { unit_id: selection.unitId }),
        api.get<CatalogList<CatalogItem>>("/disciplines"),
        api.get<CatalogList<CatalogItem>>("/work-packages", { project_context_id: selection.contextId }),
      ]);
      const label = (item: CatalogItem) => (item.code ? `${item.code} · ${item.name}` : item.name);
      options.value = {
        responsibles: responsibles.items.map((item) => ({ id: item.id, label: item.name })),
        areas: areas.items.map((item) => ({ id: item.id, label: label(item) })),
        disciplines: disciplines.items.map((item) => ({ id: item.id, label: label(item) })),
        workPackages: workPackages.items.map((item) => ({ id: item.id, label: label(item) })),
      };
      step.value = "mapping";
    } catch (caught) {
      error.value = message(caught, "Não foi possível carregar os cadastros do Hub.");
    } finally {
      busy.value = false;
    }
  }

  function setMapping(section: MappingSection, source: string, targetId: string): void {
    // "Sem correspondente" remove a entrada: o valor fica sem mapping e o plano o bloqueia.
    const next = Object.fromEntries(
      Object.entries(mapping.value[section]).filter(([key]) => key !== source),
    );
    if (targetId) next[source] = targetId;
    mapping.value = { ...mapping.value, [section]: next };
  }

  async function buildPlan(): Promise<void> {
    if (!batch.value) return;
    busy.value = true;
    error.value = "";
    stale.value = false;
    try {
      plan.value = await api.post<ImportPlan>(`${BASE}/batches/${batch.value.batchId}/plan`, {
        mapping: mapping.value,
      });
      step.value = "plan";
    } catch (caught) {
      error.value = message(caught, "Não foi possível montar o plano.");
    } finally {
      busy.value = false;
    }
  }

  /** O backend reconstrói o plano e compara o hash: mudou algo, volta para revisão (PLAN_STALE). */
  async function apply(): Promise<void> {
    if (!batch.value || !plan.value?.canApply) return;
    busy.value = true;
    error.value = "";
    stale.value = false;
    try {
      result.value = await api.post<ImportApplyResult>(`${BASE}/batches/${batch.value.batchId}/apply`, {
        mapping: mapping.value,
        planSha256: plan.value.planSha256,
      });
      step.value = "result";
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 409) {
        stale.value = true;
        plan.value = null;
        error.value = "Os dados mudaram desde que o plano foi gerado. Revise o plano novamente.";
      } else {
        error.value = message(caught, "Não foi possível aplicar a importação.");
      }
    } finally {
      busy.value = false;
    }
  }

  function reset(): void {
    step.value = "source";
    file.value = null;
    batch.value = null;
    mapping.value = emptyMapping();
    plan.value = null;
    result.value = null;
    error.value = "";
    stale.value = false;
  }

  return {
    step,
    units,
    contexts,
    profiles,
    selection,
    file,
    batch,
    mapping,
    options,
    plan,
    result,
    busy,
    error,
    stale,
    selectedContext,
    hasProgress,
    loadSetup,
    loadContexts,
    selectFile,
    analyze,
    loadMappingOptions,
    setMapping,
    buildPlan,
    apply,
    reset,
  };
}

export type EquipmentImport = ReturnType<typeof useEquipmentImport>;
