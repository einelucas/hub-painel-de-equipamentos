import { mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import CatalogAdmin from "~/components/admin/CatalogAdmin.vue";
import { useConfirm } from "~/composables/useConfirm";
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
  const del = vi.fn().mockResolvedValue(undefined);
  vi.stubGlobal("useApi", () => ({ get, patch, post, delete: del }));

  const wrapper = mount(CatalogAdmin, {
    props: { path: "/disciplines", label: "Disciplinas", hasCode: true, ...overrides },
  });
  return { wrapper, get, patch, post, del };
}

async function settle(wrapper: ReturnType<typeof mount>) {
  await new Promise((resolve) => setTimeout(resolve));
  await wrapper.vm.$nextTick();
}

afterEach(() => {
  useConfirm().cancel();
  vi.unstubAllGlobals();
});

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

    expect(wrapper.get(".modal-card h2").text()).toBe("Editar registro");
    expect(wrapper.get(".modal-card").find("form").exists()).toBe(true);
    await wrapper.get("form input[maxlength='200']").setValue("Elétrica industrial");
    await wrapper.get("form").trigger("submit");
    await settle(wrapper);

    expect(wrapper.find(".modal-card").exists()).toBe(false);
    expect(patch).toHaveBeenCalledWith("/disciplines/c-1", {
      code: "EL",
      name: "Elétrica industrial",
    });
  });

  it("desativa com confirmação no diálogo do Hub", async () => {
    const { wrapper, patch } = mountAdmin();
    await settle(wrapper);

    const toggle = wrapper
      .get("[data-testid='catalog-item-c-1']")
      .findAll("button")
      .find((button) => button.text().includes("Desativar"));
    await toggle!.trigger("click");
    await wrapper.vm.$nextTick();

    expect(useConfirm().state.open).toBe(true);
    expect(useConfirm().state.message).toContain("Elétrica");
    useConfirm().accept();
    await settle(wrapper);

    expect(patch).toHaveBeenCalledWith("/disciplines/c-1", { active: false });
  });

  it("exclui um registro após confirmação, usando o endpoint do catálogo", async () => {
    const { wrapper, del, get } = mountAdmin();
    await settle(wrapper);
    expect(get).toHaveBeenCalledTimes(1);

    const removeButton = wrapper
      .get("[data-testid='catalog-item-c-1']")
      .findAll("button")
      .find((button) => button.text().includes("Excluir"));
    await removeButton!.trigger("click");
    await wrapper.vm.$nextTick();

    expect(useConfirm().state.open).toBe(true);
    expect(useConfirm().state.title).toBe("Zona de risco");
    useConfirm().accept();
    await settle(wrapper);

    expect(del).toHaveBeenCalledWith("/disciplines/c-1");
    expect(get).toHaveBeenCalledTimes(2);
  });

  it("mantém o registro quando a exclusão é cancelada", async () => {
    const { wrapper, del } = mountAdmin();
    await settle(wrapper);

    const removeButton = wrapper
      .get("[data-testid='catalog-item-c-1']")
      .findAll("button")
      .find((button) => button.text().includes("Excluir"));
    await removeButton!.trigger("click");
    await wrapper.vm.$nextTick();
    useConfirm().cancel();
    await settle(wrapper);

    expect(del).not.toHaveBeenCalled();
  });

  it("reativa registro inativo sem pedir confirmação", async () => {
    const { wrapper, patch } = mountAdmin();
    await settle(wrapper);

    const toggle = wrapper
      .get("[data-testid='catalog-item-c-2']")
      .findAll("button")
      .find((button) => button.text().includes("Reativar"));
    await toggle!.trigger("click");
    await settle(wrapper);

    expect(useConfirm().state.open).toBe(false);
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

  it("edita a descrição opcional de Work Package", async () => {
    const { wrapper, patch } = mountAdmin({
      path: "/work-packages",
      label: "Work Packages",
      hasDescription: true,
    });
    await settle(wrapper);

    const edit = wrapper
      .get("[data-testid='catalog-item-c-1']")
      .findAll("button")
      .find((button) => button.text().includes("Editar"));
    await edit!.trigger("click");
    await wrapper.get("form textarea").setValue("Instalações elétricas provisórias");
    await wrapper.get("form").trigger("submit");
    await settle(wrapper);

    expect(patch).toHaveBeenCalledWith("/work-packages/c-1", {
      code: "EL",
      name: "Elétrica",
      description: "Instalações elétricas provisórias",
    });
  });

  it("cria etiqueta com a cor escolhida", async () => {
    const { wrapper, post } = mountAdmin({
      path: "/criticality-labels",
      label: "Criticidades",
      hasCode: false,
      hasColor: true,
    });
    await settle(wrapper);
    await wrapper.get(".catalog-header button").trigger("click");
    expect(wrapper.get(".modal-card h2").text()).toBe("Novo registro em Criticidades");
    await wrapper.get("form input[maxlength='200']").setValue("Urgente");
    await wrapper.get("form input[type='color']").setValue("#cc3344");
    await wrapper.get("form").trigger("submit");
    await settle(wrapper);

    expect(post).toHaveBeenCalledWith("/criticality-labels", {
      name: "Urgente",
      color: "#cc3344",
    });
  });
});

describe("CatalogAdmin · contextos de projeto", () => {
  function contexts(): CatalogItem[] {
    return [
      { id: "pc-1", name: "Fase 1", code: "F1", active: true },
      { id: "pc-2", name: "Fase 2", code: "F2", active: true },
    ];
  }

  function mountContexts() {
    const get = vi.fn().mockResolvedValue({ items: contexts() });
    const patch = vi.fn().mockResolvedValue({});
    const post = vi.fn().mockResolvedValue({});
    const del = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("useApi", () => ({ get, patch, post, delete: del }));
    const wrapper = mount(CatalogAdmin, {
      props: {
        path: "/units/u-1/project-contexts",
        itemPath: "/project-contexts",
        label: "Contextos",
        hasCode: true,
      },
    });
    return { wrapper, get, patch, post, del };
  }

  async function editItem(wrapper: ReturnType<typeof mount>, id: string) {
    const edit = wrapper
      .get(`[data-testid='catalog-item-${id}']`)
      .findAll("button")
      .find((button) => button.text().includes("Editar"));
    await edit!.trigger("click");
  }

  it("não exibe nem edita prefixo EAP (legado removido na P1.3.1)", async () => {
    const { wrapper, patch } = mountContexts();
    await settle(wrapper);
    expect(wrapper.text()).not.toContain("Prefixo EAP");
    await editItem(wrapper, "pc-2");
    expect(wrapper.find("[data-testid='catalog-eap-prefix']").exists()).toBe(false);
    await wrapper.get("form").trigger("submit");
    await settle(wrapper);
    expect(patch).toHaveBeenCalledWith("/project-contexts/pc-2", { name: "Fase 2", code: "F2" });
  });

  it("desativar contexto também usa a rota de edição do contexto", async () => {
    const { wrapper, patch } = mountContexts();
    await settle(wrapper);

    const toggle = wrapper
      .get("[data-testid='catalog-item-pc-1']")
      .findAll("button")
      .find((button) => button.text().includes("Desativar"));
    await toggle!.trigger("click");
    await wrapper.vm.$nextTick();
    useConfirm().accept();
    await settle(wrapper);

    expect(patch).toHaveBeenCalledWith("/project-contexts/pc-1", { active: false });
  });

  it("exclui contexto pela rota própria, não pela rota da unidade", async () => {
    const { wrapper, del } = mountContexts();
    await settle(wrapper);

    const removeButton = wrapper
      .get("[data-testid='catalog-item-pc-1']")
      .findAll("button")
      .find((button) => button.text().includes("Excluir"));
    await removeButton!.trigger("click");
    await wrapper.vm.$nextTick();
    useConfirm().accept();
    await settle(wrapper);

    expect(del).toHaveBeenCalledWith("/project-contexts/pc-1");
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
