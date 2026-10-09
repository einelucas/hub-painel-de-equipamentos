import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import EquipmentForm from "~/components/equipment/EquipmentForm.vue";
import type { EapNodeItem, Equipment } from "~/types/equipment";

const process: EapNodeItem = {
  id: "eap-process",
  code: "04",
  name: "Geração de Energia",
  level: "PROCESS",
  parentId: "island",
  active: true,
  createdAt: "2026-10-01T00:00:00",
  updatedAt: "2026-10-01T00:00:00",
};
const area: EapNodeItem = {
  ...process,
  id: "eap-area",
  code: "04.A",
  name: "Casa de Força",
  level: "AREA",
  parentId: process.id,
};
const island: EapNodeItem = {
  ...process,
  id: "island",
  code: "UTI",
  name: "Utilidades",
  level: "ISLAND",
  parentId: null,
};
const workPackages = ["CIV004", "CIV012", "CIV015", "CAL003", "CAL005", "CAL006"].map(
  (code, index) => ({ id: `wp-${index}`, code, name: code, active: true }),
);

function equipment(): Equipment {
  return {
    id: "eq-1",
    name: "Isolamento térmico",
    origin: null,
    startupAt: null,
    criticality: null,
    currentStage: 0,
    stageName: "Nova demanda",
    capexEstimated: null,
    projectContext: { id: "ctx-1", name: "Caldeira 4" },
    unit: { id: "unit-1", name: "Nova Mutum" },
    discipline: null,
    eapNode: area,
    area: { id: "legacy-area", name: "Área legada" },
    workPackage: null,
    workPackages,
    responsibleUser: null,
    supplier: null,
    operationalStatus: "ACTIVE",
    projectTotalValue: null,
    contractualDeliveryStart: null,
    contractualDeliveryEnd: null,
    componentsCount: 0,
    calculated: {
      maxLeadTimeDays: null,
      maxPreStartDays: null,
      maxFreightDays: null,
      deliveryDeadline: null,
      contractOrderDeadline: null,
      negotiationDeadline: null,
      negotiationDaysRemaining: null,
      negotiationStatus: null,
      workNeedDaysRemaining: null,
      workNeedStatus: null,
    },
    createdAt: "2026-10-01T00:00:00",
    updatedAt: "2026-10-01T00:00:00",
  };
}

async function settle(wrapper: ReturnType<typeof mount>): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve));
  await wrapper.vm.$nextTick();
}

describe("EquipmentForm", () => {
  it("edita pela EAP canônica e preserva os seis Work Packages N:N", async () => {
    const current = equipment();
    const get = vi.fn(async (path: string) => {
      if (path === "/units/unit-1/project-contexts") {
        return { items: [{ id: "ctx-1", name: "Caldeira 4", active: true }] };
      }
      if (path === "/disciplines" || path === "/responsibles") return { items: [] };
      if (path === "/work-packages") return { items: workPackages };
      if (path === "/eap-nodes") return { items: [process, area, island] };
      throw new Error(`GET inesperado: ${path}`);
    });
    const patch = vi.fn().mockResolvedValue(current);
    vi.stubGlobal("useApi", () => ({ get, post: vi.fn(), patch }));
    vi.stubGlobal("useAuthStore", () => ({ can: () => true }));

    const wrapper = mount(EquipmentForm, {
      props: { unitId: "unit-1", equipment: current },
    });
    await settle(wrapper);

    expect(get).toHaveBeenCalledWith("/eap-nodes", { active: true });
    expect(get).toHaveBeenCalledWith("/work-packages");
    expect(get).not.toHaveBeenCalledWith("/work-packages", expect.anything());
    expect(wrapper.get("[data-testid='edit-eaps']").text()).toContain("Editar EAPs");

    const eapSelect = wrapper.get("[data-testid='eap-node-select']");
    expect((eapSelect.element as HTMLInputElement).value).toBe("04.A · Casa de Força");
    await eapSelect.trigger("focus");
    const eapMenu = wrapper.get("[role='listbox']");
    expect(eapMenu.text()).toContain("04 · Geração de Energia");
    expect(eapMenu.text()).toContain("04.A · Casa de Força");
    expect(eapMenu.text()).not.toContain("UTI · Utilidades");

    expect(wrapper.findAll("[aria-label^='Remover CAL']")).toHaveLength(3);
    expect(wrapper.findAll("[aria-label^='Remover CIV']")).toHaveLength(3);

    await wrapper.get("form").trigger("submit");
    expect(patch).toHaveBeenCalledWith(
      "/equipments/eq-1",
      expect.objectContaining({
        eapNodeId: "eap-area",
        workPackageIds: workPackages.map((item) => item.id),
      }),
    );
    expect(patch.mock.calls[0]![1]).not.toHaveProperty("areaId");
  });
});
