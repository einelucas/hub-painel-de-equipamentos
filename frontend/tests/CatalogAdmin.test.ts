import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import CatalogAdmin from "~/components/admin/CatalogAdmin.vue";
import type { CatalogItem } from "~/types/equipment";

function items(): CatalogItem[] {
  return [
    { id: "c-1", name: "Elétrica", code: "EL", active: true },
    { id: "c-2", name: "Mecânica", code: "ME", active: false },
  ];
}

function mountAdmin(overrides: Record<string, unknown> = {}) {
  const get = vi.fn().mockResolvedValue({ items: items() });
  const patch = vi.fn().mockResolvedValue({});
  const post = vi.fn().mockResolvedValue({});
  vi.stubGlobal("useApi", () => ({ get, patch, post }));

  const wrapper = mount(CatalogAdmin, {
    props: { path: "/disciplines", label: "Disciplinas", hasCode: true, ...overrides },
  });
  return { wrapper, get, patch, post };
}

async function settle(wrapper: ReturnType<typeof mount>) {
  await new Promise((resolve) => setTimeout(resolve));
  await wrapper.vm.$nextTick();
}

describe("CatalogAdmin", () => {
  it("lista o catálogo com a situação de cada registro", async () => {
    const { wrapper, get } = mountAdmin();
    await settle(wrapper);

    // Visão administrativa: inclui inativos para permitir reativar.
    expect(get).toHaveBeenCalledWith("/disciplines", { include_inactive: "true" });
    expect(wrapper.get("[data-testid='catalog-item-c-1']").text()).toContain("Ativo");
    expect(wrapper.get("[data-testid='catalog-item-c-2']").text()).toContain("Inativo");
  });

  it("edita um registro pelo endpoint existente, sem criar rota nova", async () => {
    const { wrapper, patch } = mountAdmin();
    await settle(wrapper);

    const edit = wrapper
      .get("[data-testid='catalog-item-c-1']")
      .findAll("button")
      .find((button) => button.text().includes("Editar"));
    await edit!.trigger("click");

    await wrapper.get("form input[maxlength='200']").setValue("Elétrica industrial");
    await wrapper.get("form").trigger("submit");
    await settle(wrapper);

    expect(patch).toHaveBeenCalledWith("/disciplines/c-1", {
      code: "EL",
      name: "Elétrica industrial",
    });
  });

  it("desativa em vez de excluir, confirmando antes", async () => {
    vi.stubGlobal("confirm", vi.fn().mockReturnValue(true));
    const { wrapper, patch } = mountAdmin();
    await settle(wrapper);

    const toggle = wrapper
      .get("[data-testid='catalog-item-c-1']")
      .findAll("button")
      .find((button) => button.text().includes("Desativar"));
    await toggle!.trigger("click");
    await settle(wrapper);

    expect(patch).toHaveBeenCalledWith("/disciplines/c-1", { active: false });
    // Nada de exclusão física: nenhum DELETE é oferecido.
    expect(wrapper.html()).not.toContain("Excluir");
  });

  it("reativa registro inativo sem pedir confirmação", async () => {
    const confirmSpy = vi.fn().mockReturnValue(true);
    vi.stubGlobal("confirm", confirmSpy);
    const { wrapper, patch } = mountAdmin();
    await settle(wrapper);

    const toggle = wrapper
      .get("[data-testid='catalog-item-c-2']")
      .findAll("button")
      .find((button) => button.text().includes("Reativar"));
    await toggle!.trigger("click");
    await settle(wrapper);

    expect(confirmSpy).not.toHaveBeenCalled();
    expect(patch).toHaveBeenCalledWith("/disciplines/c-2", { active: true });
  });

  it("avisa quando depende de um pai ainda não selecionado", async () => {
    const { wrapper, get } = mountAdmin({
      requiresParent: "Selecione uma unidade no filtro do módulo.",
    });
    await settle(wrapper);

    expect(get).not.toHaveBeenCalled();
    expect(wrapper.get("[data-testid='catalog-blocked']").text()).toContain("Selecione uma unidade");
  });
});

describe("CatalogAdmin · prefixo EAP dos contextos", () => {
  function contexts(): CatalogItem[] {
    return [
      { id: "pc-1", name: "Fase 1", code: "F1", eapPrefix: "23", active: true },
      { id: "pc-2", name: "Fase 2", code: "F2", eapPrefix: null, active: true },
    ];
  }

  function mountContexts() {
    const get = vi.fn().mockResolvedValue({ items: contexts() });
    const patch = vi.fn().mockResolvedValue({});
    const post = vi.fn().mockResolvedValue({});
    vi.stubGlobal("useApi", () => ({ get, patch, post }));
    const wrapper = mount(CatalogAdmin, {
      props: {
        path: "/units/u-1/project-contexts",
        itemPath: "/project-contexts",
        label: "Contextos",
        hasCode: true,
        hasEapPrefix: true,
      },
    });
    return { wrapper, get, patch, post };
  }

  async function editItem(wrapper: ReturnType<typeof mount>, id: string) {
    const edit = wrapper
      .get(`[data-testid='catalog-item-${id}']`)
      .findAll("button")
      .find((button) => button.text().includes("Editar"));
    await edit!.trigger("click");
  }

  it("mostra o prefixo definido e 'Não definido' quando é nulo", async () => {
    const { wrapper } = mountContexts();
    await settle(wrapper);

    expect(wrapper.get("[data-testid='catalog-item-pc-1']").text()).toContain("Prefixo EAP: 23");
    expect(wrapper.get("[data-testid='catalog-item-pc-2']").text()).toContain("Prefixo EAP: Não definido");
  });

  it("edita o prefixo pela rota de contexto, preservando zero à esquerda", async () => {
    const { wrapper, patch } = mountContexts();
    await settle(wrapper);
    await editItem(wrapper, "pc-2");

    const input = wrapper.get("[data-testid='catalog-eap-prefix']");
    expect((input.element as HTMLInputElement).value).toBe("");
    await input.setValue("03");
    await wrapper.get("form").trigger("submit");
    await settle(wrapper);

    expect(patch).toHaveBeenCalledWith("/project-contexts/pc-2", { name: "Fase 2", code: "F2", eapPrefix: "03" });
  });

  it("limpar o campo envia null, nunca string vazia", async () => {
    const { wrapper, patch } = mountContexts();
    await settle(wrapper);
    await editItem(wrapper, "pc-1");

    await wrapper.get("[data-testid='catalog-eap-prefix']").setValue("  ");
    await wrapper.get("form").trigger("submit");
    await settle(wrapper);

    expect(patch).toHaveBeenCalledWith("/project-contexts/pc-1", { name: "Fase 1", code: "F1", eapPrefix: null });
  });

  it("recusa prefixo com caracteres não numéricos sem chamar a API", async () => {
    const { wrapper, patch } = mountContexts();
    await settle(wrapper);
    await editItem(wrapper, "pc-1");

    await wrapper.get("[data-testid='catalog-eap-prefix']").setValue("23.A");
    await wrapper.get("form").trigger("submit");
    await settle(wrapper);

    expect(patch).not.toHaveBeenCalled();
    expect(wrapper.get("[role='alert']").text()).toContain("Prefixo EAP deve conter só dígitos");
  });

  it("desativar contexto também usa a rota de edição do contexto", async () => {
    vi.stubGlobal("confirm", vi.fn().mockReturnValue(true));
    const { wrapper, patch } = mountContexts();
    await settle(wrapper);

    const toggle = wrapper
      .get("[data-testid='catalog-item-pc-1']")
      .findAll("button")
      .find((button) => button.text().includes("Desativar"));
    await toggle!.trigger("click");
    await settle(wrapper);

    expect(patch).toHaveBeenCalledWith("/project-contexts/pc-1", { active: false });
  });

  it("outros catálogos não exibem nem enviam prefixo EAP", async () => {
    const { wrapper, patch } = mountAdmin();
    await settle(wrapper);
    expect(wrapper.find("[data-testid='catalog-item-eap-prefix']").exists()).toBe(false);

    const edit = wrapper
      .get("[data-testid='catalog-item-c-1']")
      .findAll("button")
      .find((button) => button.text().includes("Editar"));
    await edit!.trigger("click");
    expect(wrapper.find("[data-testid='catalog-eap-prefix']").exists()).toBe(false);
    await wrapper.get("form").trigger("submit");
    await settle(wrapper);
    expect(patch).toHaveBeenCalledWith("/disciplines/c-1", { code: "EL", name: "Elétrica" });
  });
});
