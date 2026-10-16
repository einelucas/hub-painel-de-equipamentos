import { computed, reactive, ref } from "vue";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useQueue } from "~/composables/useQueue";

beforeEach(() => {
  vi.stubGlobal("ref", ref);
  vi.stubGlobal("reactive", reactive);
  vi.stubGlobal("computed", computed);
});

afterEach(() => vi.unstubAllGlobals());

describe("useQueue", () => {
  it("mantém Unidade, Obra e Equipamento na URL e na requisição da fila", async () => {
    const replace = vi.fn().mockResolvedValue(undefined);
    const initialize = vi.fn().mockResolvedValue(undefined);
    const get = vi.fn().mockResolvedValue({
      items: [],
      pagination: { page: 1, pageSize: 25, total: 0, totalPages: 0 },
    });
    vi.stubGlobal("useRoute", () => ({ query: { view: "compact" } }));
    vi.stubGlobal("useRouter", () => ({ replace }));
    vi.stubGlobal("useApi", () => ({ get }));
    vi.stubGlobal("useModuleContextStore", () => ({
      selectedUnit: "unit-1",
      selectedProjectContext: "project-1",
      selectedEquipment: "equipment-1",
      apiQuery: {
        unit_id: "unit-1",
        project_context_id: "project-1",
        equipment_id: "equipment-1",
      },
      initialize,
    }));

    const queue = useQueue("engineering");
    await queue.initialize({
      unit: "unit-1",
      project: "project-1",
      equipment: "equipment-1",
    });

    expect(initialize).toHaveBeenCalledWith({
      unit: "unit-1",
      project: "project-1",
      equipment: "equipment-1",
    });
    expect(replace).toHaveBeenCalledWith({
      query: {
        view: "compact",
        unit: "unit-1",
        project: "project-1",
        equipment: "equipment-1",
      },
    });
    expect(get).toHaveBeenCalledWith("/queues/engineering", {
      unit_id: "unit-1",
      project_context_id: "project-1",
      equipment_id: "equipment-1",
      page: 1,
      pageSize: 25,
    });
  });
});
