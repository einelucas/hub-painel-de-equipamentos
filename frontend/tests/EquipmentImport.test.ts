import { mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import ImportAnalysisStep from "~/components/imports/ImportAnalysisStep.vue";
import ImportEquipmentButton from "~/components/imports/ImportEquipmentButton.vue";
import ImportEquipmentModal from "~/components/imports/ImportEquipmentModal.vue";
import ImportMappingStep from "~/components/imports/ImportMappingStep.vue";
import ImportPlanStep from "~/components/imports/ImportPlanStep.vue";
import ImportResultStep from "~/components/imports/ImportResultStep.vue";
import ImportSourceStep from "~/components/imports/ImportSourceStep.vue";
import { isXlsx } from "~/composables/useEquipmentImport";
import { ApiError } from "~/services/api/error";
import type { ImportApplyResult, ImportBatch, ImportPlan } from "~/types/imports";

// Dados 100% sintéticos.
const UNITS = [{ id: "u-tst", code: "TST", name: "Unidade Teste", active: true }];
const CONTEXTS = [{ id: "pc-a", code: "PA", name: "Projeto Sintético A", unitId: "u-tst", eapPrefix: "03", active: true }];
const PROFILES = [{ profileId: "monday-equipamentos-legacy", version: 1, sourceSystem: "monday", description: "Board de equipamentos do Monday" }];

function batch(overrides: Partial<ImportBatch> = {}): ImportBatch {
  return {
    batchId: "b-1",
    alreadyStaged: false,
    status: "STAGED",
    projectContextId: "pc-a",
    fileName: "board-sintetico.xlsx",
    fileSha256: "a".repeat(64),
    boardTitle: "Equipamentos - Projeto Sintético",
    sheetName: "Planilha",
    profile: { profileId: "monday-equipamentos-legacy", version: 1, sha256: "b".repeat(64) },
    equipments: 2,
    components: 3,
    warnings: 1,
    errors: 0,
    unknownFields: ["equipment:Coluna Nova"],
    fragileIdentities: 1,
    unknownStatuses: 0,
    canProceed: true,
    issues: [
      { severity: "warning", code: "fragile_equipment_identity", message: "Identidade por nome", rowNumber: 4, field: "name" },
    ],
    sourceValues: { responsibles: ["Responsável Origem A"], areas: ["Área Origem"], disciplines: [], workPackages: [] },
    ...overrides,
  };
}

function plan(overrides: Partial<ImportPlan> = {}): ImportPlan {
  return {
    batchId: "b-1",
    projectContextId: "pc-a",
    mappingSha256: "c".repeat(64),
    planSha256: "d".repeat(64),
    mappingIssues: [],
    groups: [
      { name: "Equipamentos", create: 2, update: 0, noop: 0, blocked: 0 },
      { name: "Componentes", create: 3, update: 0, noop: 0, blocked: 0 },
    ],
    blocked: [],
    warnings: [],
    hasBlocked: false,
    canApply: true,
    ...overrides,
  };
}

function applyResult(overrides: Partial<ImportApplyResult> = {}): ImportApplyResult {
  return {
    migrationRunId: "run-1",
    status: "APPLIED",
    created: 5,
    updated: 0,
    unchanged: 0,
    reconciliation: { equipmentsCompared: 2, componentsCompared: 3, mismatches: 0, pendingMapping: 0, divergences: [] },
    hasDivergences: false,
    ...overrides,
  };
}

interface ApiOverrides {
  upload?: () => Promise<unknown>;
  plan?: () => Promise<unknown>;
  apply?: () => Promise<unknown>;
}

function setup(permissions = ["equipments:write"], overrides: ApiOverrides = {}, selectedUnit = "u-tst") {
  const get = vi.fn(async (path: string) => {
    const table: Record<string, unknown> = {
      "/units": { items: UNITS },
      "/imports/monday/profiles": { items: PROFILES },
      "/units/u-tst/project-contexts": { items: CONTEXTS },
      "/responsibles": { items: [{ id: "user-a", name: "Usuário Sintético A", email: "usuario.a@example.test" }] },
      "/areas": { items: [{ id: "area-a", name: "Área Sintética", active: true }] },
      "/disciplines": { items: [] },
      "/work-packages": { items: [] },
    };
    return table[path] ?? { items: [] };
  });
  const upload = vi.fn(
    async (_path: string, _form: FormData, _method?: string) => (overrides.upload ?? (async () => batch()))(),
  );
  const post = vi.fn(async (path: string) => {
    if (path.endsWith("/plan")) return (overrides.plan ?? (async () => plan()))();
    if (path.endsWith("/apply")) return (overrides.apply ?? (async () => applyResult()))();
    throw new Error(`rota inesperada ${path}`);
  });
  vi.stubGlobal("useApi", () => ({ get, post, upload }));
  vi.stubGlobal("useAuthStore", () => ({ can: (permission: string) => permissions.includes(permission) }));
  vi.stubGlobal("useModuleContextStore", () => ({ selectedUnit }));
  return { get, post, upload };
}

function mountButton() {
  return mount(ImportEquipmentButton, {
    global: {
      components: {
        ImportEquipmentModal,
        ImportSourceStep,
        ImportAnalysisStep,
        ImportMappingStep,
        ImportPlanStep,
        ImportResultStep,
      },
      stubs: { AppModal: { props: ["open", "title"], emits: ["close"], template: "<div v-if='open'><button data-testid='modal-close' @click=\"$emit('close')\" /><slot /></div>" } },
    },
  });
}

async function settle(wrapper: ReturnType<typeof mount>) {
  for (let i = 0; i < 5; i += 1) {
    await new Promise((resolve) => setTimeout(resolve));
    await wrapper.vm.$nextTick();
  }
}

async function chooseFile(wrapper: ReturnType<typeof mount>, name = "board-sintetico.xlsx") {
  const input = wrapper.get("[data-testid='import-file']");
  Object.defineProperty(input.element, "files", { value: [new File(["conteudo"], name)], configurable: true });
  await input.trigger("change");
}

async function openAndAnalyze(wrapper: ReturnType<typeof mount>) {
  await wrapper.get("[data-testid='nav-import']").trigger("click");
  await settle(wrapper);
  await chooseFile(wrapper);
  await wrapper.get("[data-testid='import-analyze']").trigger("click");
  await settle(wrapper);
}

async function goToPlan(wrapper: ReturnType<typeof mount>) {
  await openAndAnalyze(wrapper);
  await wrapper.get("[data-testid='import-to-mapping']").trigger("click");
  await settle(wrapper);
  await wrapper.get("[data-testid='import-build-plan']").trigger("click");
  await settle(wrapper);
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("Importar equipamentos", () => {
  it("botão aparece com equipments:write e não é link de navegação", async () => {
    setup();
    const wrapper = mountButton();
    const button = wrapper.get("[data-testid='nav-import']");
    expect(button.element.tagName).toBe("BUTTON");
    expect(button.attributes("href")).toBeUndefined();
    expect(button.attributes("aria-label")).toBe("Importar equipamentos");
  });

  it("VIEWER (sem equipments:write) não vê o botão", () => {
    setup(["equipments:read"]);
    expect(mountButton().find("[data-testid='nav-import']").exists()).toBe(false);
  });

  it("abre o modal com unidade do módulo, obra única e formato pré-selecionados", async () => {
    const { get } = setup();
    const wrapper = mountButton();
    await wrapper.get("[data-testid='nav-import']").trigger("click");
    await settle(wrapper);

    expect(wrapper.find("[data-testid='import-wizard']").exists()).toBe(true);
    expect(get).toHaveBeenCalledWith("/imports/monday/profiles");
    expect((wrapper.get("[data-testid='import-unit']").element as HTMLSelectElement).value).toBe("u-tst");
    expect((wrapper.get("[data-testid='import-context']").element as HTMLSelectElement).value).toBe("pc-a");
    expect(wrapper.get("[data-testid='import-profile-single']").text()).toContain("Board de equipamentos do Monday");
  });

  it("permite trocar unidade e obra antes do upload", async () => {
    const { get } = setup(["equipments:write"], {}, "");
    const wrapper = mountButton();
    await wrapper.get("[data-testid='nav-import']").trigger("click");
    await settle(wrapper);
    expect((wrapper.get("[data-testid='import-context']").element as HTMLSelectElement).disabled).toBe(true);

    await wrapper.get("[data-testid='import-unit']").setValue("u-tst");
    await settle(wrapper);
    expect(get).toHaveBeenCalledWith("/units/u-tst/project-contexts");
    expect((wrapper.get("[data-testid='import-context']").element as HTMLSelectElement).value).toBe("pc-a");
  });

  it("recusa extensão diferente de .xlsx sem enviar nada", async () => {
    const { upload } = setup();
    const wrapper = mountButton();
    await wrapper.get("[data-testid='nav-import']").trigger("click");
    await settle(wrapper);
    await chooseFile(wrapper, "planilha.csv");

    expect(wrapper.get("[data-testid='import-error']").text()).toContain(".xlsx");
    expect((wrapper.get("[data-testid='import-analyze']").element as HTMLButtonElement).disabled).toBe(true);
    expect(upload).not.toHaveBeenCalled();
    expect(isXlsx("A.XLSX") && !isXlsx("a.xls") && !isXlsx("a.zip")).toBe(true);
  });

  it("envia o arquivo como multipart e mostra o resumo da análise", async () => {
    const { upload } = setup();
    const wrapper = mountButton();
    await openAndAnalyze(wrapper);

    const [path, form, method] = upload.mock.calls[0]!;
    expect(path).toBe("/imports/monday/batches");
    expect(method).toBe("POST");
    expect(form.get("projectContextId")).toBe("pc-a");
    expect(form.get("profileId")).toBe("monday-equipamentos-legacy");
    expect(wrapper.get("[data-testid='import-equipments']").text()).toBe("2");
    expect(wrapper.get("[data-testid='import-components']").text()).toBe("3");
    expect(wrapper.get("[data-testid='import-warning-list']").text()).toContain("linha 4");
  });

  it("mostra carregamento durante a análise", async () => {
    let release: (value: unknown) => void = () => {};
    setup(["equipments:write"], { upload: () => new Promise((resolve) => (release = resolve)) });
    const wrapper = mountButton();
    await wrapper.get("[data-testid='nav-import']").trigger("click");
    await settle(wrapper);
    await chooseFile(wrapper);
    await wrapper.get("[data-testid='import-analyze']").trigger("click");
    await wrapper.vm.$nextTick();
    expect(wrapper.get("[data-testid='import-analyze']").text()).toContain("Analisando");
    release(batch());
    await settle(wrapper);
    expect(wrapper.find("[data-testid='import-step-analysis']").exists()).toBe(true);
  });

  it("arquivo já analisado é sinalizado sem duplicar", async () => {
    setup(["equipments:write"], { upload: async () => batch({ alreadyStaged: true }) });
    const wrapper = mountButton();
    await openAndAnalyze(wrapper);
    expect(wrapper.find("[data-testid='import-already-staged']").exists()).toBe(true);
  });

  it("erros impedem avançar para o mapeamento", async () => {
    setup(["equipments:write"], {
      upload: async () =>
        batch({
          errors: 1,
          canProceed: false,
          issues: [{ severity: "error", code: "invalid_date", message: "Data inválida", rowNumber: 5, field: "startup_at" }],
        }),
    });
    const wrapper = mountButton();
    await openAndAnalyze(wrapper);
    expect(wrapper.get("[data-testid='import-error-list']").text()).toContain("Data inválida");
    expect(wrapper.find("[data-testid='import-cannot-proceed']").exists()).toBe(true);
    expect((wrapper.get("[data-testid='import-to-mapping']").element as HTMLButtonElement).disabled).toBe(true);
  });

  it("mapping usa cadastros existentes e envia escolhas ao plano", async () => {
    const { get, post } = setup();
    const wrapper = mountButton();
    await openAndAnalyze(wrapper);
    await wrapper.get("[data-testid='import-to-mapping']").trigger("click");
    await settle(wrapper);

    expect(get).toHaveBeenCalledWith("/responsibles", { unit_id: "u-tst" });
    expect(get).toHaveBeenCalledWith("/work-packages", { project_context_id: "pc-a" });
    expect(wrapper.find("[data-testid='mapping-disciplines']").exists()).toBe(false); // sem valores na origem
    await wrapper.get("[data-testid='mapping-select-responsibles']").setValue("user-a");
    await wrapper.get("[data-testid='mapping-select-areas']").setValue("area-a");
    await wrapper.get("[data-testid='import-build-plan']").trigger("click");
    await settle(wrapper);

    expect(post).toHaveBeenCalledWith("/imports/monday/batches/b-1/plan", {
      mapping: {
        responsibles: { "Responsável Origem A": "user-a" },
        areas: { "Área Origem": "area-a" },
        disciplines: {},
        workPackages: {},
      },
    });
    expect(wrapper.get("[data-testid='plan-group-Equipamentos']").text()).toContain("2");
  });

  it("plano com BLOCKED desabilita a confirmação e lista o motivo", async () => {
    setup(["equipments:write"], {
      plan: async () =>
        plan({
          hasBlocked: true,
          canApply: false,
          groups: [{ name: "Equipamentos", create: 1, update: 0, noop: 0, blocked: 1 }],
          blocked: [
            { group: "Equipamentos", sourceKey: "k", label: "Equipamento Sintético B", issues: [{ code: "unmapped_area", message: "Área sem mapeamento" }] },
          ],
        }),
    });
    const wrapper = mountButton();
    await goToPlan(wrapper);
    expect(wrapper.get("[data-testid='plan-blocked']").text()).toContain("Área sem mapeamento");
    expect(wrapper.get("[data-testid='confirm-blocked']").text()).toBe("1");
    expect((wrapper.get("[data-testid='import-confirm']").element as HTMLButtonElement).disabled).toBe(true);
  });

  it("confirmação mostra o resumo e aplica com o hash do plano", async () => {
    const { post } = setup();
    const wrapper = mountButton();
    await goToPlan(wrapper);
    const summary = wrapper.get("[data-testid='import-confirm-summary']").text();
    expect(summary).toContain("PA · Projeto Sintético A");
    expect(summary).toContain("board-sintetico.xlsx");

    await wrapper.get("[data-testid='import-confirm']").trigger("click");
    await settle(wrapper);
    expect(post).toHaveBeenCalledWith(
      "/imports/monday/batches/b-1/apply",
      expect.objectContaining({ planSha256: "d".repeat(64) }),
    );
    expect(wrapper.get("[data-testid='import-result-title']").text()).toBe("Importação concluída");
    expect(wrapper.get("[data-testid='result-created']").text()).toBe("5");
  });

  it("PLAN_STALE (409) volta para revisão do plano", async () => {
    setup(["equipments:write"], {
      apply: async () => {
        throw new ApiError("PLAN_STALE", 409, { error: "PLAN_STALE" });
      },
    });
    const wrapper = mountButton();
    await goToPlan(wrapper);
    await wrapper.get("[data-testid='import-confirm']").trigger("click");
    await settle(wrapper);
    expect(wrapper.find("[data-testid='import-stale']").exists()).toBe(true);
    expect((wrapper.get("[data-testid='import-confirm']").element as HTMLButtonElement).disabled).toBe(true);
    expect(wrapper.find("[data-testid='import-step-result']").exists()).toBe(false);
  });

  it("divergência na reconciliação nunca aparece como sucesso", async () => {
    setup(["equipments:write"], {
      apply: async () =>
        applyResult({
          hasDivergences: true,
          reconciliation: {
            equipmentsCompared: 2,
            componentsCompared: 3,
            mismatches: 1,
            pendingMapping: 0,
            divergences: [{ equipment: "Equipamento Sintético A", field: "startup_at", hubValue: "2027-10-27", sourceValue: "2027-10-28" }],
          },
        }),
    });
    const wrapper = mountButton();
    await goToPlan(wrapper);
    await wrapper.get("[data-testid='import-confirm']").trigger("click");
    await settle(wrapper);
    expect(wrapper.get("[data-testid='import-result-title']").text()).toBe("Importação aplicada com divergências");
    expect(wrapper.get("[data-testid='result-divergences']").text()).toContain("startup_at");
  });

  it("fechar no meio pede confirmação; reabrir reinicia o wizard", async () => {
    const confirmSpy = vi.fn().mockReturnValue(true);
    vi.stubGlobal("confirm", confirmSpy);
    setup();
    const wrapper = mountButton();
    await openAndAnalyze(wrapper);
    await wrapper.get("[data-testid='modal-close']").trigger("click");
    await settle(wrapper);
    expect(confirmSpy).toHaveBeenCalledTimes(1);
    expect(wrapper.find("[data-testid='import-wizard']").exists()).toBe(false);

    await wrapper.get("[data-testid='nav-import']").trigger("click");
    await settle(wrapper);
    expect(wrapper.find("[data-testid='import-step-source']").exists()).toBe(true);
  });

  it("fixtures não contêm dado corporativo", () => {
    const text = JSON.stringify({ UNITS, CONTEXTS, PROFILES, batch: batch(), plan: plan(), result: applyResult() });
    expect(text).not.toMatch(/@inpasa|inpasa\.com/i);
    expect(text).not.toMatch(/\b(LEM|RDN|NMT|RVD|C2|F2)\b/);
  });
});
