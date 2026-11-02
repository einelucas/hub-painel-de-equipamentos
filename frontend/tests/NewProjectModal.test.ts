import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import NewProjectModal from "~/components/project-creation/NewProjectModal.vue";

const catalog = {
  areas: [{ id: "area-1", name: "Utilidades", isUnassigned: false, active: true }],
  equipments: [
    {
      id: "equipment-1",
      name: "Sistema de ar",
      areaIds: ["area-1"],
      active: true,
      reviewFlags: [],
      components: [
        { id: "component-1", name: "Compressor", active: true, requiresQuantityReview: false, requiresNameReview: false },
        { id: "component-inactive", name: "Componente inativo", active: false, requiresQuantityReview: false, requiresNameReview: false },
      ],
    },
    {
      id: "equipment-2",
      name: "Secador",
      areaIds: ["area-1"],
      active: true,
      reviewFlags: [],
      components: [
        { id: "component-2", name: "Filtro", active: true, requiresQuantityReview: false, requiresNameReview: false },
      ],
    },
  ],
};

function setup() {
  const get = vi.fn(async (path: string) => {
    if (path === "/units") return { items: [{ id: "unit-1", name: "Unidade 1", active: true }] };
    if (path === "/master-catalog") return catalog;
    throw new Error(`GET inesperado: ${path}`);
  });
  vi.stubGlobal("useApi", () => ({ get, post: vi.fn() }));
  vi.stubGlobal("useModuleContextStore", () => ({ setUnit: vi.fn(), setProjectContext: vi.fn() }));

  return mount(NewProjectModal, {
    props: { open: false, initialUnitId: "unit-1" },
    global: {
      stubs: {
        NuxtLink: { template: "<a><slot /></a>" },
        AppModal: {
          props: ["open", "title"],
          template: "<div v-if='open'><h2>{{ title }}</h2><slot /></div>",
        },
      },
    },
  });
}

async function advance(wrapper: ReturnType<typeof setup>): Promise<void> {
  await wrapper.get("[data-testid='new-project-next']").trigger("click");
  await flushPromises();
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("wizard de nova obra", () => {
  it("mantém equipamentos e componentes ao navegar entre as etapas", async () => {
    const wrapper = setup();
    await wrapper.setProps({ open: true });
    await flushPromises();

    await wrapper.get("[data-testid='new-project-name'] input").setValue("Obra teste");
    expect((wrapper.get("[data-testid='new-project-name'] input").element as HTMLInputElement).value).toBe("Obra teste");
    expect((wrapper.get("[data-testid='new-project-unit'] input").element as HTMLInputElement).value).toBe("unit-1");
    expect(wrapper.get("[data-testid='new-project-next']").attributes("disabled")).toBeUndefined();
    await advance(wrapper);

    expect(wrapper.get(".project-steps .v-stepper-item--selected").text()).toContain("Equipamentos");
    expect(wrapper.find(".search").exists()).toBe(false);
    expect(wrapper.get("[data-testid='new-project-equipment-search']").classes()).toContain("search-field");
    expect(wrapper.text()).toContain("1 comp.");

    await wrapper.get("[data-testid='select-equipment-equipment-1']").trigger("change");
    await wrapper.get("[data-testid='select-equipment-equipment-2']").trigger("change");
    await advance(wrapper);

    expect(wrapper.findAll(".component-group")).toHaveLength(2);
    expect(wrapper.text()).toContain("Compressor");
    expect(wrapper.text()).toContain("Filtro");
    expect(wrapper.text()).not.toContain("Componente inativo");

    await wrapper.get("[data-testid='select-component-component-1']").trigger("change");
    await advance(wrapper);
    expect(wrapper.text()).toContain("1 componentes");
    expect(wrapper.text()).toContain("Compressor");

    await wrapper.get("[data-testid='new-project-back']").trigger("click");
    expect(wrapper.get("[data-testid='select-component-component-1']").attributes("checked")).toBeDefined();
    expect(wrapper.findAll(".component-group")).toHaveLength(2);
  });
});
