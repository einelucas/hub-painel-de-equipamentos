import { mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import ProjectContextAdmin from "~/components/admin/ProjectContextAdmin.vue";
import type { CatalogItem, Unit } from "~/types/equipment";

// Dados 100% sintéticos (nenhuma unidade, obra, pessoa ou prefixo real).
const UNITS: Unit[] = [
  { id: "u-tst", code: "TST", name: "Unidade Teste", active: true },
  { id: "u-tst2", code: "TS2", name: "Unidade Teste 2", active: true },
];
function contexts(): CatalogItem[] {
  return [
    { id: "pc-a", code: "PA", name: "Projeto Sintético A", unitId: "u-tst", eapPrefix: "03", active: true },
    { id: "pc-b", code: "PB", name: "Projeto Sintético B", unitId: "u-tst", eapPrefix: null, active: false },
  ];
}

type Routes = Record<string, unknown | (() => unknown)>;

function apiMock(routes: Routes = {}) {
  const table: Routes = {
    "/units": { items: UNITS },
    "/units/u-tst/project-contexts": { items: contexts() },
    "/units/u-tst2/project-contexts": { items: [] },
    "/areas": { items: [{ id: "a1", name: "Área Sintética", active: true }, { id: "a2", name: "Área Antiga", active: false }] },
    "/disciplines": { items: [{ id: "d1", name: "Disciplina Sintética", code: "DS", active: true }] },
    "/work-packages": { items: [{ id: "w1", name: "Pacote Sintético", code: "WP-S1", active: true }] },
    ...routes,
  };
  const get = vi.fn(async (path: string) => {
    const value = table[path];
    if (value instanceof Error) throw value;
    return typeof value === "function" ? (value as () => unknown)() : (value ?? { items: [] });
  });
  const post = vi.fn().mockResolvedValue({ id: "pc-new", code: "PN", name: "Projeto Novo", eapPrefix: null, active: true });
  const patch = vi.fn().mockResolvedValue({});
  vi.stubGlobal("useApi", () => ({ get, post, patch }));
  return { get, post, patch };
}

function stubAuth(permissions: string[] = ["catalogs:manage", "users:manage"]) {
  vi.stubGlobal("useAuthStore", () => ({ can: (permission: string) => permissions.includes(permission) }));
}

async function settle(wrapper: ReturnType<typeof mount>) {
  for (let i = 0; i < 4; i += 1) {
    await new Promise((resolve) => setTimeout(resolve));
    await wrapper.vm.$nextTick();
  }
}

function mountAdmin(unitId = "u-tst") {
  return mount(ProjectContextAdmin, { props: { unitId } });
}

function itemButton(wrapper: ReturnType<typeof mount>, id: string, label: string) {
  return wrapper
    .get(`[data-testid='project-item-${id}']`)
    .findAll("button")
    .find((button) => button.text().includes(label));
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("ProjectContextAdmin", () => {
  it("lista as unidades no seletor e emite a troca de unidade", async () => {
    apiMock();
    stubAuth();
    const wrapper = mountAdmin();
    await settle(wrapper);

    const options = wrapper.get("[data-testid='project-unit']").findAll("option").map((o) => o.text());
    expect(options).toEqual(["Selecione", "TST · Unidade Teste", "TS2 · Unidade Teste 2"]);

    await wrapper.get("[data-testid='project-unit']").setValue("u-tst2");
    expect(wrapper.emitted("update:unitId")?.[0]).toEqual(["u-tst2"]);
  });

  it("sem unidade mostra estado vazio e não oferece criação", async () => {
    const { get } = apiMock();
    stubAuth();
    const wrapper = mountAdmin("");
    await settle(wrapper);

    expect(wrapper.get("[data-testid='project-no-unit']").text()).toContain(
      "Selecione ou cadastre uma unidade antes de criar um contexto.",
    );
    expect(wrapper.find("[data-testid='project-new']").exists()).toBe(false);
    expect(get).not.toHaveBeenCalledWith(expect.stringContaining("/project-contexts"));
  });

  it("lista os contextos com código, nome, prefixo e situação", async () => {
    const { get } = apiMock();
    stubAuth();
    const wrapper = mountAdmin();
    await settle(wrapper);

    expect(get).toHaveBeenCalledWith("/units/u-tst/project-contexts");
    const active = wrapper.get("[data-testid='project-item-pc-a']").text();
    expect(active).toContain("PA");
    expect(active).toContain("Projeto Sintético A");
    expect(active).toContain("Prefixo EAP 03");
    expect(active).toContain("Ativo");
    const inactive = wrapper.get("[data-testid='project-item-pc-b']");
    expect(inactive.text()).toContain("Prefixo EAP não definido");
    expect(inactive.text()).toContain("Inativo");
    expect(inactive.classes()).toContain("inactive");
  });

  it("mostra o resumo de preparação só com dados das APIs existentes", async () => {
    const { get } = apiMock();
    stubAuth();
    const wrapper = mountAdmin();
    await settle(wrapper);

    expect(get).toHaveBeenCalledWith("/areas", { unit_id: "u-tst" });
    expect(get).toHaveBeenCalledWith("/work-packages", { project_context_id: "pc-a" });
    expect(wrapper.get("[data-testid='readiness-eap']").text()).toBe("Definido (03)");
    expect(wrapper.get("[data-testid='readiness-areas']").text()).toBe("1 ativas · 2 cadastradas");
    expect(wrapper.get("[data-testid='readiness-disciplines']").text()).toBe("1 ativas");
    expect(wrapper.get("[data-testid='readiness-work-packages']").text()).toBe("1 cadastrados");

    await wrapper.get("[data-testid='project-item-pc-b'] .project-card").trigger("click");
    await settle(wrapper);
    // Prefixo ausente é informativo: nada de erro nem bloqueio.
    expect(wrapper.get("[data-testid='readiness-eap']").text()).toBe("Não definido");
    expect(wrapper.find("[data-testid='project-readiness'] [role='alert']").exists()).toBe(false);
  });

  it("cria contexto na unidade selecionada; prefixo vazio vai como null", async () => {
    const { post } = apiMock();
    stubAuth();
    const wrapper = mountAdmin();
    await settle(wrapper);

    await wrapper.get("[data-testid='project-new']").trigger("click");
    await wrapper.get("[data-testid='project-code']").setValue("PN");
    await wrapper.get("[data-testid='project-name']").setValue("Projeto Novo");
    await wrapper.get("[data-testid='project-eap-prefix']").setValue("   ");
    await wrapper.get("[data-testid='project-form']").trigger("submit");
    await settle(wrapper);

    expect(post).toHaveBeenCalledWith("/units/u-tst/project-contexts", {
      code: "PN",
      name: "Projeto Novo",
      eapPrefix: null,
    });
    expect(wrapper.emitted("changed")).toBeTruthy();
  });

  it("edita pelo endpoint do contexto preservando zero à esquerda (texto, não número)", async () => {
    const { patch } = apiMock();
    stubAuth();
    const wrapper = mountAdmin();
    await settle(wrapper);

    await itemButton(wrapper, "pc-b", "Editar")!.trigger("click");
    const prefix = wrapper.get("[data-testid='project-eap-prefix']");
    expect(prefix.attributes("type")).toBe("text");
    await prefix.setValue("007");
    await wrapper.get("[data-testid='project-form']").trigger("submit");
    await settle(wrapper);

    expect(patch).toHaveBeenCalledWith("/project-contexts/pc-b", {
      code: "PB",
      name: "Projeto Sintético B",
      eapPrefix: "007",
    });
  });

  it("aceita prefixo numérico e reativa pelo checkbox Ativo na edição", async () => {
    const { patch } = apiMock();
    stubAuth();
    const wrapper = mountAdmin();
    await settle(wrapper);

    await itemButton(wrapper, "pc-b", "Editar")!.trigger("click");
    await wrapper.get("[data-testid='project-eap-prefix']").setValue("24");
    await wrapper.get("[data-testid='project-active']").setValue(true);
    await wrapper.get("[data-testid='project-form']").trigger("submit");
    await settle(wrapper);

    expect(patch).toHaveBeenCalledWith("/project-contexts/pc-b", {
      code: "PB",
      name: "Projeto Sintético B",
      eapPrefix: "24",
      active: true,
    });
  });

  it("recusa prefixo inválido sem chamar a API", async () => {
    const { patch, post } = apiMock();
    stubAuth();
    const wrapper = mountAdmin();
    await settle(wrapper);

    await itemButton(wrapper, "pc-a", "Editar")!.trigger("click");
    await wrapper.get("[data-testid='project-eap-prefix']").setValue("2A");
    await wrapper.get("[data-testid='project-form']").trigger("submit");
    await settle(wrapper);

    expect(patch).not.toHaveBeenCalled();
    expect(post).not.toHaveBeenCalled();
    expect(wrapper.get("[data-testid='project-form'] [role='alert']").text()).toContain("só dígitos");
  });

  it("limpar o prefixo na edição envia null e nunca copia de outro contexto", async () => {
    const { patch } = apiMock();
    stubAuth();
    const wrapper = mountAdmin();
    await settle(wrapper);

    await itemButton(wrapper, "pc-a", "Editar")!.trigger("click");
    await wrapper.get("[data-testid='project-eap-prefix']").setValue("");
    await wrapper.get("[data-testid='project-form']").trigger("submit");
    await settle(wrapper);
    expect(patch).toHaveBeenCalledWith("/project-contexts/pc-a", {
      code: "PA",
      name: "Projeto Sintético A",
      eapPrefix: null,
    });

    // Novo contexto começa sem prefixo, mesmo existindo outro contexto com "03".
    await wrapper.get("[data-testid='project-new']").trigger("click");
    expect((wrapper.get("[data-testid='project-eap-prefix']").element as HTMLInputElement).value).toBe("");
  });

  it("desativa com confirmação e reativa sem confirmação", async () => {
    const confirmSpy = vi.fn().mockReturnValue(true);
    vi.stubGlobal("confirm", confirmSpy);
    const { patch } = apiMock();
    stubAuth();
    const wrapper = mountAdmin();
    await settle(wrapper);

    await itemButton(wrapper, "pc-a", "Desativar")!.trigger("click");
    await settle(wrapper);
    expect(confirmSpy).toHaveBeenCalledTimes(1);
    expect(patch).toHaveBeenCalledWith("/project-contexts/pc-a", { active: false });

    await itemButton(wrapper, "pc-b", "Reativar")!.trigger("click");
    await settle(wrapper);
    expect(confirmSpy).toHaveBeenCalledTimes(1);
    expect(patch).toHaveBeenCalledWith("/project-contexts/pc-b", { active: true });
  });

  it("mostra carregamento enquanto a lista não chega", async () => {
    let release: (value: unknown) => void = () => {};
    apiMock({ "/units/u-tst/project-contexts": () => new Promise((resolve) => (release = resolve)) });
    stubAuth();
    const wrapper = mountAdmin();
    await settle(wrapper);

    expect(wrapper.text()).toContain("Carregando contextos...");
    release({ items: contexts() });
    await settle(wrapper);
    expect(wrapper.text()).not.toContain("Carregando contextos...");
  });

  it("mostra erro da API sem quebrar o painel", async () => {
    apiMock({ "/units/u-tst/project-contexts": new Error("Falha sintética ao listar") });
    stubAuth();
    const wrapper = mountAdmin();
    await settle(wrapper);

    expect(wrapper.get("[role='alert']").text()).toContain("Falha sintética ao listar");
  });

  it("unidade sem contextos mostra estado vazio", async () => {
    apiMock();
    stubAuth();
    const wrapper = mountAdmin("u-tst2");
    await settle(wrapper);

    expect(wrapper.get("[data-testid='project-empty']").text()).toContain("Nenhum contexto de projeto nesta unidade.");
  });

  it("ações contextuais só pedem a seção existente (sem CRUD duplicado)", async () => {
    apiMock();
    stubAuth();
    const wrapper = mountAdmin();
    await settle(wrapper);

    await wrapper.get("[data-testid='goto-areas']").trigger("click");
    await wrapper.get("[data-testid='goto-work-packages']").trigger("click");
    await wrapper.get("[data-testid='goto-access']").trigger("click");
    expect(wrapper.emitted("navigate")).toEqual([
      [{ section: "catalogs", catalog: "areas" }],
      [{ section: "catalogs", catalog: "workPackages", contextId: "pc-a" }],
      [{ section: "access" }],
    ]);
  });

  it("sem catalogs:manage não exibe criação, edição nem gerenciamento", async () => {
    apiMock();
    stubAuth([]);
    const wrapper = mountAdmin();
    await settle(wrapper);

    expect(wrapper.find("[data-testid='project-new']").exists()).toBe(false);
    expect(wrapper.text()).not.toContain("Editar");
    expect(wrapper.text()).not.toContain("Desativar");
    expect(wrapper.find("[data-testid='goto-areas']").exists()).toBe(false);
    expect(wrapper.find("[data-testid='goto-access']").exists()).toBe(false);
  });

  it("fixtures não contêm dado corporativo", () => {
    const text = JSON.stringify({ UNITS, contexts: contexts() });
    expect(text).not.toMatch(/@inpasa|inpasa\.com/i);
    expect(text).not.toMatch(/\b(LEM|RDN|NMT|RVD)\b/);
    expect(text).not.toMatch(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i);
  });
});
