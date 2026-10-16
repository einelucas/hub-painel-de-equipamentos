import { createPinia, setActivePinia } from "pinia";
import { computed, ref } from "vue";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useModuleContextStore } from "~/stores/moduleContext";

const units = [
  { id: "unit-1", name: "Unidade 1", active: true },
  { id: "unit-2", name: "Unidade 2", active: true },
];
const contexts = {
  "unit-1": [{ id: "project-1", unitId: "unit-1", name: "Obra 1", active: true }],
  "unit-2": [{ id: "project-2", unitId: "unit-2", name: "Obra 2", active: true }],
};
const equipments = {
  "unit-1": [{ id: "equipment-1", name: "Equipamento 1" }],
  "unit-2": [{ id: "equipment-2", name: "Equipamento 2" }],
};

function setup(defaults: {
  firstAccess: boolean;
  unitId: string | null;
  projectContextId: string | null;
}) {
  const get = vi.fn(async (path: string, query?: Record<string, unknown>) => {
    if (path === "/units") return { items: units };
    if (path === "/module-context/defaults") {
      return { ...defaults, firstAccessAt: "2026-10-16T12:00:00Z" };
    }
    if (path.includes("/project-contexts")) {
      const unitId = path.split("/")[2] as keyof typeof contexts;
      return { items: contexts[unitId] ?? [] };
    }
    if (path === "/equipments") {
      const unitId = query?.unit_id as keyof typeof equipments;
      const items = equipments[unitId] ?? [];
      return {
        items,
        pagination: { page: 1, pageSize: 100, total: items.length, totalPages: 1 },
      };
    }
    throw new Error(`GET inesperado: ${path}`);
  });
  vi.stubGlobal("useApi", () => ({ get }));
  return { store: useModuleContextStore(), get };
}

beforeEach(() => {
  setActivePinia(createPinia());
  vi.stubGlobal("ref", ref);
  vi.stubGlobal("computed", computed);
});

afterEach(() => vi.unstubAllGlobals());

describe("contexto global do módulo", () => {
  it("mantém todas as unidades e obras no primeiro acesso", async () => {
    const { store } = setup({ firstAccess: true, unitId: null, projectContextId: null });

    await store.initialize();

    expect(store.selectedUnit).toBe("");
    expect(store.selectedProjectContext).toBe("");
    expect(store.selectedEquipment).toBe("");
  });

  it("seleciona a obra inicial devolvida pela API nos acessos seguintes", async () => {
    const { store } = setup({
      firstAccess: false,
      unitId: "unit-2",
      projectContextId: "project-2",
    });

    await store.initialize();

    expect(store.selectedUnit).toBe("unit-2");
    expect(store.selectedProjectContext).toBe("project-2");
  });

  it("prioriza a URL e preserva os filtros quando a aba seguinte não traz query", async () => {
    const { store } = setup({
      firstAccess: false,
      unitId: "unit-2",
      projectContextId: "project-2",
    });

    await store.initialize({
      unit: "unit-1",
      project: "project-1",
      equipment: "equipment-1",
    });
    await store.initialize({});

    expect(store.selectedUnit).toBe("unit-1");
    expect(store.selectedProjectContext).toBe("project-1");
    expect(store.selectedEquipment).toBe("equipment-1");
    expect(store.apiQuery).toEqual({
      unit_id: "unit-1",
      project_context_id: "project-1",
      equipment_id: "equipment-1",
    });
  });
});
