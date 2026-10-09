import { mount } from "@vue/test-utils";
import { watch } from "vue";
import { afterEach, describe, expect, it, vi } from "vitest";
import AdminPanel from "~/components/admin/AdminPanel.vue";
import CatalogAdmin from "~/components/admin/CatalogAdmin.vue";
import EapTreeAdmin from "~/components/admin/EapTreeAdmin.vue";
import EquipmentAdmin from "~/components/admin/EquipmentAdmin.vue";
import ProjectContextAdmin from "~/components/admin/ProjectContextAdmin.vue";

// Dados 100% sintéticos.
const ROUTES: Record<string, unknown> = {
  "/units": { items: [{ id: "u-tst", code: "TST", name: "Unidade Teste", active: true }] },
  "/units/u-tst/project-contexts": {
    items: [{ id: "pc-a", code: "PA", name: "Projeto Sintético A", unitId: "u-tst", active: true }],
  },
  "/eap-nodes": {
    items: [{ id: "ep1", code: "01", name: "Processo Sintético", level: "PROCESS", parentId: null, active: true }],
  },
  "/disciplines": { items: [] },
  "/work-packages": { items: [] },
};

function setup(permissions: string[]) {
  const get = vi.fn(async (path: string) => ROUTES[path] ?? { items: [] });
  vi.stubGlobal("useApi", () => ({ get, post: vi.fn(), patch: vi.fn() }));
  vi.stubGlobal("useAuthStore", () => ({ can: (permission: string) => permissions.includes(permission) }));
  vi.stubGlobal("watch", watch); // auto-import do Nuxt usado pelo AdminPanel
  return { get };
}

function mountAdmin(unitId = "u-tst") {
  return mount(EquipmentAdmin, {
    props: { open: true, unitId },
    global: {
      components: { AdminPanel, CatalogAdmin, EapTreeAdmin, ProjectContextAdmin },
      stubs: {
        AppModal: { props: ["open", "title"], template: "<div v-if='open'><slot /></div>" },
        UnitAccessAdmin: { template: "<div data-testid='unit-access-admin'>acessos</div>" },
      },
    },
  });
}

async function settle(wrapper: ReturnType<typeof mount>) {
  for (let i = 0; i < 4; i += 1) {
    await new Promise((resolve) => setTimeout(resolve));
    await wrapper.vm.$nextTick();
  }
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("EquipmentAdmin", () => {
  it("usuário autorizado vê Projetos como primeira seção, depois Catálogos e Acesso", async () => {
    setup(["catalogs:manage", "users:manage"]);
    const wrapper = mountAdmin();
    await settle(wrapper);

    const tabs = wrapper.findAll("[role='tab']").map((tab) => tab.text());
    expect(tabs).toEqual(["Projetos", "Catálogos", "Acesso às unidades"]);
    expect(wrapper.get("[data-testid='admin-tab-projects']").attributes("aria-selected")).toBe("true");
    expect(wrapper.find("[data-testid='project-context-admin']").exists()).toBe(true);
  });

  it("sem catalogs:manage não há Projetos nem Catálogos; só o que a permissão permite", async () => {
    setup(["users:manage"]);
    const wrapper = mountAdmin();
    await settle(wrapper);

    expect(wrapper.find("[data-testid='admin-tab-projects']").exists()).toBe(false);
    expect(wrapper.find("[data-testid='project-context-admin']").exists()).toBe(false);
    expect(wrapper.find("[data-testid='unit-access-admin']").exists()).toBe(true);
  });

  it("sem nenhuma permissão administrativa não exibe ações de gerenciamento", async () => {
    setup([]);
    const wrapper = mountAdmin();
    await settle(wrapper);

    expect(wrapper.findAll("[role='tab']")).toHaveLength(0);
    expect(wrapper.find("[data-testid='project-new']").exists()).toBe(false);
    expect(wrapper.text()).not.toContain("Editar");
  });

  it("troca entre Projetos, Catálogos e Acesso", async () => {
    setup(["catalogs:manage", "users:manage"]);
    const wrapper = mountAdmin();
    await settle(wrapper);

    await wrapper.get("[data-testid='admin-tab-catalogs']").trigger("click");
    await settle(wrapper);
    expect(wrapper.find("[data-testid='catalog-switch-units']").exists()).toBe(true);
    // Contextos saíram do CRUD genérico: ficam só em Projetos.
    expect(wrapper.find("[data-testid='catalog-switch-contexts']").exists()).toBe(false);

    await wrapper.get("[data-testid='admin-tab-access']").trigger("click");
    await settle(wrapper);
    expect(wrapper.find("[data-testid='unit-access-admin']").exists()).toBe(true);

    await wrapper.get("[data-testid='admin-tab-projects']").trigger("click");
    await settle(wrapper);
    expect(wrapper.find("[data-testid='project-context-admin']").exists()).toBe(true);
  });

  it("'Gerenciar Work Packages' abre o catálogo corporativo sem seletor de contexto", async () => {
    const { get } = setup(["catalogs:manage", "users:manage"]);
    const wrapper = mountAdmin();
    await settle(wrapper);

    await wrapper.get("[data-testid='goto-work-packages']").trigger("click");
    await settle(wrapper);

    expect(wrapper.get("[data-testid='admin-tab-catalogs']").attributes("aria-selected")).toBe("true");
    expect(wrapper.get("[data-testid='catalog-switch-workPackages']").classes()).toContain("active");
    expect(wrapper.find("[data-testid='wp-context']").exists()).toBe(false);
    expect(get).toHaveBeenCalledWith("/work-packages", {
      include_inactive: "true",
    });
  });

  it("'Gerenciar Árvore EAP' e 'Gerenciar acessos' reutilizam as seções existentes", async () => {
    const { get } = setup(["catalogs:manage", "users:manage"]);
    const wrapper = mountAdmin();
    await settle(wrapper);

    await wrapper.get("[data-testid='goto-areas']").trigger("click");
    await settle(wrapper);
    expect(wrapper.get("[data-testid='catalog-switch-areas']").classes()).toContain("active");
    expect(get).toHaveBeenCalledWith("/eap-nodes");

    await wrapper.get("[data-testid='admin-tab-projects']").trigger("click");
    await settle(wrapper);
    await wrapper.get("[data-testid='goto-access']").trigger("click");
    await settle(wrapper);
    expect(wrapper.find("[data-testid='unit-access-admin']").exists()).toBe(true);
  });

  it("unidade escolhida em Projetos vale para os catálogos do painel, sem filtro do módulo", async () => {
    const { get } = setup(["catalogs:manage"]);
    const wrapper = mountAdmin("");
    await settle(wrapper);

    expect(wrapper.find("[data-testid='project-no-unit']").exists()).toBe(true);
    await wrapper.get("[data-testid='project-unit']").setValue("u-tst");
    await settle(wrapper);
    expect(get).toHaveBeenCalledWith("/units/u-tst/project-contexts", {
      include_inactive: "true",
    });

    await wrapper.get("[data-testid='admin-tab-catalogs']").trigger("click");
    await wrapper.get("[data-testid='catalog-switch-areas']").trigger("click");
    await settle(wrapper);
    expect(wrapper.find("[data-testid='eap-tree-admin']").exists()).toBe(true);
  });
});
