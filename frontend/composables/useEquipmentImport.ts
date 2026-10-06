import { computed, reactive, ref } from "vue";
import { ApiError } from "~/services/api/error";
import type { CatalogItem, CatalogList, EapNodeItem, Responsible, Unit } from "~/types/equipment";
import type {
  ImportApplyResult,
  ImportBatch,
  ImportFileFailure,
  ImportLocationValue,
  ImportMapping,
  ImportOption,
  ImportPlan,
  ImportProfile,
  ImportSourceValues,
  MappingSection,
} from "~/types/imports";

/**
 * Estado do wizard "Importar equipamentos" enquanto o modal está aberto.
 * O frontend só envia os arquivos e as escolhas do usuário: parsing, staging,
 * mapping, plan, apply e reconciliação acontecem no backend (motor monday_import).
 *
 * Uma importação = um ou mais XLSX da MESMA obra (ex.: um por fase ocupada do
 * board). Cada arquivo vira um batch; plano, confirmação e apply são únicos.
 */
export type ImportStep = "source" | "analysis" | "mapping" | "plan" | "result";
export const IMPORT_STEPS: { key: ImportStep; label: string }[] = [
  { key: "source", label: "Obra e arquivos" },
  { key: "analysis", label: "Análise" },
  { key: "mapping", label: "Mapeamento" },
  { key: "plan", label: "Plano" },
  { key: "result", label: "Resultado" },
];
export const MAPPING_SECTIONS: { key: MappingSection; label: string }[] = [
  { key: "responsibles", label: "Responsáveis" },
  { key: "disciplines", label: "Disciplinas" },
  { key: "workPackages", label: "Work Packages" },
  { key: "eapNodes", label: "EAP (localização)" },
];

const BASE = "/imports/monday";

export function isXlsx(fileName: string): boolean {
  return fileName.toLowerCase().endsWith(".xlsx");
}

function emptyMapping(): ImportMapping {
  return { responsibles: {}, disciplines: {}, workPackages: {}, eapNodes: {} };
}

function message(caught: unknown, fallback: string): string {
  return caught instanceof Error && caught.message ? caught.message : fallback;
}

function union(lists: string[][]): string[] {
  return [...new Set(lists.flat())].sort((a, b) => a.localeCompare(b, "pt-BR"));
}

/** Valores de origem de todos os arquivos, sem repetição (localizações somam equipamentos). */
export function mergeSourceValues(batches: ImportBatch[]): ImportSourceValues {
  const locations = new Map<string, ImportLocationValue>();
  for (const batch of batches) {
    for (const location of batch.sourceValues.locations) {
      const known = locations.get(location.value);
      locations.set(
        location.value,
        known ? { ...known, equipments: known.equipments + location.equipments } : { ...location },
      );
    }
  }
  return {
    responsibles: union(batches.map((batch) => batch.sourceValues.responsibles)),
    disciplines: union(batches.map((batch) => batch.sourceValues.disciplines)),
    workPackages: union(batches.map((batch) => batch.sourceValues.workPackages)),
    locations: [...locations.values()].sort((a, b) => a.value.localeCompare(b.value, "pt-BR")),
  };
}

export function useEquipmentImport() {
  const api = useApi();

  const step = ref<ImportStep>("source");
  const units = ref<Unit[]>([]);
  const contexts = ref<CatalogItem[]>([]);
  const profiles = ref<ImportProfile[]>([]);
  const selection = reactive({ unitId: "", contextId: "", profileId: "" });
  const files = ref<File[]>([]);
  const batches = ref<ImportBatch[]>([]);
  const failures = ref<ImportFileFailure[]>([]);
  const mapping = ref<ImportMapping>(emptyMapping());
  const options = ref<Record<MappingSection, ImportOption[]>>({
    responsibles: [],
    disciplines: [],
    workPackages: [],
    eapNodes: [],
  });
  const plan = ref<ImportPlan | null>(null);
  const result = ref<ImportApplyResult | null>(null);
  const busy = ref(false);
  const error = ref("");
  const stale = ref(false);

  const selectedContext = computed(() => contexts.value.find((item) => item.id === selection.contextId) ?? null);
  const hasProgress = computed(() => batches.value.length > 0 && result.value === null);
  const sourceValues = computed(() => mergeSourceValues(batches.value));
  const totals = computed(() => ({
    equipments: batches.value.reduce((sum, batch) => sum + batch.equipments, 0),
    components: batches.value.reduce((sum, batch) => sum + batch.components, 0),
  }));
  /** Só segue com TODOS os arquivos analisados sem erro (nunca importa um conjunto parcial). */
  const canProceed = computed(
    () => batches.value.length > 0 && failures.value.length === 0 && batches.value.every((batch) => batch.canProceed),
  );

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

  /** Vários .xlsx de uma vez (um por fase). ZIP e outros formatos são recusados. */
  function selectFiles(candidates: File[]): void {
    error.value = "";
    const invalid = candidates.filter((candidate) => !isXlsx(candidate.name));
    if (invalid.length) {
      files.value = [];
      error.value = `Envie apenas arquivos .xlsx exportados do Monday (recusado: ${invalid.map((f) => f.name).join(", ")}).`;
      return;
    }
    const unique = new Map(candidates.map((candidate) => [`${candidate.name}:${candidate.size}`, candidate]));
    files.value = [...unique.values()];
  }

  async function analyze(): Promise<void> {
    if (!files.value.length || !selection.contextId || !selection.profileId) return;
    busy.value = true;
    error.value = "";
    batches.value = [];
    failures.value = [];
    try {
      // Sequencial: cada arquivo é um staging próprio (hash, batch, issues).
      for (const candidate of files.value) {
        const form = new FormData();
        form.append("projectContextId", selection.contextId);
        form.append("profileId", selection.profileId);
        form.append("file", candidate, candidate.name);
        try {
          const staged = await api.upload<ImportBatch>(`${BASE}/batches`, form, "POST");
          if (!batches.value.some((batch) => batch.batchId === staged.batchId)) batches.value.push(staged);
        } catch (caught) {
          failures.value.push({ fileName: candidate.name, message: message(caught, "Falha ao analisar.") });
        }
      }
      mapping.value = emptyMapping();
      plan.value = null;
      if (batches.value.length || failures.value.length) step.value = "analysis";
    } finally {
      busy.value = false;
    }
  }

  /** Alvos do mapping vêm dos catálogos existentes; nada é criado aqui. */
  async function loadMappingOptions(): Promise<void> {
    busy.value = true;
    error.value = "";
    try {
      const [responsibles, disciplines, workPackages, eapNodes] = await Promise.all([
        api.get<CatalogList<Responsible>>("/responsibles", { unit_id: selection.unitId }),
        api.get<CatalogList<CatalogItem>>("/disciplines"),
        api.get<CatalogList<CatalogItem>>("/work-packages", { project_context_id: selection.contextId }),
        api.get<CatalogList<EapNodeItem>>("/eap-nodes", { active: true }),
      ]);
      const label = (item: CatalogItem) => (item.code ? `${item.code} · ${item.name}` : item.name);
      options.value = {
        responsibles: responsibles.items.map((item) => ({ id: item.id, label: item.name })),
        disciplines: disciplines.items.map((item) => ({ id: item.id, label: label(item) })),
        workPackages: workPackages.items.map((item) => ({ id: item.id, label: label(item) })),
        // Equipamento referencia PROCESS ou AREA; o código exibido é só EapNode.code.
        eapNodes: eapNodes.items
          .filter((item) => item.level === "PROCESS" || item.level === "AREA")
          .map((item) => ({ id: item.id, label: `${item.code} · ${item.name}` })),
      };
      step.value = "mapping";
    } catch (caught) {
      error.value = message(caught, "Não foi possível carregar os cadastros do Hub.");
    } finally {
      busy.value = false;
    }
  }

  function setMapping(section: MappingSection, source: string, targetId: string): void {
    // "Sem correspondente"/"Automático" remove a entrada: vale a regra do backend.
    const next = Object.fromEntries(
      Object.entries(mapping.value[section]).filter(([key]) => key !== source),
    );
    if (targetId) next[source] = targetId;
    mapping.value = { ...mapping.value, [section]: next };
  }

  function batchIds(): string[] {
    return batches.value.map((batch) => batch.batchId);
  }

  async function buildPlan(): Promise<void> {
    if (!batches.value.length) return;
    busy.value = true;
    error.value = "";
    stale.value = false;
    try {
      plan.value = await api.post<ImportPlan>(`${BASE}/plan`, { batchIds: batchIds(), mapping: mapping.value });
      step.value = "plan";
    } catch (caught) {
      error.value = message(caught, "Não foi possível montar o plano.");
    } finally {
      busy.value = false;
    }
  }

  /** O backend reconstrói o plano e compara o hash: mudou algo, volta para revisão (PLAN_STALE). */
  async function apply(): Promise<void> {
    if (!batches.value.length || !plan.value?.canApply) return;
    busy.value = true;
    error.value = "";
    stale.value = false;
    try {
      result.value = await api.post<ImportApplyResult>(`${BASE}/apply`, {
        batchIds: batchIds(),
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
    files.value = [];
    batches.value = [];
    failures.value = [];
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
    files,
    batches,
    failures,
    mapping,
    options,
    plan,
    result,
    busy,
    error,
    stale,
    selectedContext,
    hasProgress,
    sourceValues,
    totals,
    canProceed,
    loadSetup,
    loadContexts,
    selectFiles,
    analyze,
    loadMappingOptions,
    setMapping,
    buildPlan,
    apply,
    reset,
  };
}

export type EquipmentImport = ReturnType<typeof useEquipmentImport>;
