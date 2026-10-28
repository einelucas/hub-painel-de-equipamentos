import { mount } from "@vue/test-utils";
import { ref } from "vue";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import QueueShell from "~/components/queue/QueueShell.vue";

beforeEach(() => vi.stubGlobal("ref", ref));
afterEach(() => vi.unstubAllGlobals());

describe("QueueShell", () => {
  it("disponibiliza o seletor de Obra nos filtros das filas", () => {
    const wrapper = mount(QueueShell, {
      props: {
        title: "Engenharia",
        description: "Descrição",
        criteria: "Critério",
        loading: true,
        refreshing: false,
        error: "",
        empty: true,
        pagination: null,
        page: 1,
        allowed: true,
        showSearch: false,
      },
      global: {
        stubs: {
          ModuleFilters: {
            props: { showProjectContext: Boolean },
            template: "<div data-testid='module-filters' :data-project='String(showProjectContext)'><slot /></div>",
          },
        },
      },
    });

    expect(wrapper.get("[data-testid='module-filters']").attributes("data-project")).toBe("true");
    expect(wrapper.find("input[placeholder='Nome do equipamento']").exists()).toBe(false);
    expect(wrapper.text()).not.toContain("Buscar");
  });

  it("preserva a busca nas filas que não a desativam", () => {
    const wrapper = mount(QueueShell, {
      props: {
        title: "Engenharia",
        description: "Descrição",
        criteria: "Critério",
        loading: true,
        refreshing: false,
        error: "",
        empty: true,
        pagination: null,
        page: 1,
        allowed: true,
      },
      global: {
        stubs: {
          ModuleFilters: { template: "<div><slot /></div>" },
        },
      },
    });

    expect(wrapper.get("input[placeholder='Nome do equipamento']").attributes("placeholder")).toBe("Nome do equipamento");
    expect(wrapper.text()).toContain("Buscar");
  });
});
