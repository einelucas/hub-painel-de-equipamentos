import { mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import ModuleFilters from "~/components/ModuleFilters.vue";

const store = {
  units: [{ id: "unit-1", name: "Unidade 1" }],
  projectContexts: [],
  equipmentOptions: [],
  selectedUnit: "unit-1",
  selectedProjectContext: "",
  selectedEquipment: "",
  loading: false,
  optionsLoading: false,
  setUnit: vi.fn(),
  setProjectContext: vi.fn(),
  setEquipment: vi.fn(),
};

beforeEach(() => {
  vi.useFakeTimers();
  vi.stubGlobal("useModuleContextStore", () => store);
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

function mountFilters(props: Record<string, unknown> = {}) {
  return mount(ModuleFilters, {
    props: { autoRefreshMs: 1000, ...props },
    global: { stubs: { FloatingFilterSelect: true } },
  });
}

describe("ModuleFilters", () => {
  it("não exibe mais o botão manual de atualização", () => {
    const wrapper = mountFilters();
    expect(wrapper.text()).not.toContain("Atualizar");
    wrapper.unmount();
  });

  it("emite refresh automaticamente e pausa enquanto já existe uma atualização em curso", async () => {
    const wrapper = mountFilters();

    await vi.advanceTimersByTimeAsync(1000);
    expect(wrapper.emitted("refresh")).toHaveLength(1);

    await wrapper.setProps({ refreshing: true });
    await vi.advanceTimersByTimeAsync(2000);
    expect(wrapper.emitted("refresh")).toHaveLength(1);

    await wrapper.setProps({ refreshing: false });
    await vi.advanceTimersByTimeAsync(1000);
    expect(wrapper.emitted("refresh")).toHaveLength(2);

    wrapper.unmount();
  });
});
