import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import EquipmentForm from "~/components/equipment/EquipmentForm.vue";
import type { EapNodeItem, Equipment } from "~/types/equipment";
import {
  menuElement,
  menuOptions,
  openMenu,
  shownValue,
} from "./support/searchableSelect";

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
    criticalityLabel: { id: "crit-1", name: "Médio 90~180", color: "#777ae5" },
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

/** Mocks de catálogo compartilhados pelos testes de Origem. */
function formMocks(current: Equipment | null) {
  const get = vi.fn(async (path: string) => {
    if (path === "/units/unit-1/project-contexts") {
      return { items: [{ id: "ctx-1", name: "Caldeira 4", active: true }] };
    }
    if (path === "/disciplines" || path === "/responsibles") return { items: [] };
    if (path === "/criticality-labels") return { items: [] };
    if (path === "/work-packages") return { items: workPackages };
    if (path === "/eap-nodes") return { items: [process, area, island] };
    throw new Error(`GET inesperado: ${path}`);
  });
  const patch = vi.fn().mockResolvedValue(current);
  vi.stubGlobal("useApi", () => ({ get, post: vi.fn(), patch }));
  vi.stubGlobal("useAuthStore", () => ({ can: () => true }));
  return { get, patch };
}

async function mountForm(current: Equipment | null) {
  const { patch } = formMocks(current);
  const wrapper = mount(EquipmentForm, {
    props: current ? { unitId: "unit-1", equipment: current } : { unitId: "unit-1" },
  });
  await settle(wrapper);
  return { wrapper, patch };
}

describe("EquipmentForm", () => {
  it("edita pela EAP canônica e preserva os seis Work Packages N:N", async () => {
    const current = equipment();
    const get = vi.fn(async (path: string) => {
      if (path === "/units/unit-1/project-contexts") {
        return { items: [{ id: "ctx-1", name: "Caldeira 4", active: true }] };
      }
      if (path === "/disciplines" || path === "/responsibles") return { items: [] };
      if (path === "/criticality-labels") {
        return { items: [{ id: "crit-1", name: "Médio 90~180", color: "#777ae5", active: true }] };
      }
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
    expect(get).toHaveBeenCalledWith("/criticality-labels");
    expect(get).not.toHaveBeenCalledWith("/work-packages", expect.anything());
    expect(wrapper.get("[data-testid='edit-eaps']").text()).toContain("Editar EAPs");

    expect(shownValue(wrapper, "eap-node-select")).toBe("04.A · Casa de Força");
    await openMenu(wrapper, "eap-node-select");
    const eapMenu = menuElement(wrapper, "eap-node-select");
    expect(eapMenu?.textContent).toContain("04 · Geração de Energia");
    expect(eapMenu?.textContent).toContain("04.A · Casa de Força");
    expect(eapMenu?.textContent).not.toContain("UTI · Utilidades");

    expect(wrapper.findAll("[aria-label^='Remover CAL']")).toHaveLength(3);
    expect(wrapper.findAll("[aria-label^='Remover CIV']")).toHaveLength(3);

    await wrapper.get("form").trigger("submit");
    expect(patch).toHaveBeenCalledWith(
      "/equipments/eq-1",
      expect.objectContaining({
        eapNodeId: "eap-area",
        workPackageIds: workPackages.map((item) => item.id),
        criticalityLabelId: "crit-1",
      }),
    );
    expect(patch.mock.calls[0]![1]).not.toHaveProperty("areaId");
  });

  it("Origem segue o seletor padrão e preserva o valor antigo fora do vocabulário", async () => {
    const current = { ...equipment(), origin: "Importado" };
    const { wrapper, patch } = await mountForm(current);

    expect(shownValue(wrapper, "origin-select")).toBe("Importado");

    await openMenu(wrapper, "origin-select");
    const menu = menuElement(wrapper, "origin-select");
    expect(menu?.textContent).toContain("Nacional");
    expect(menu?.textContent).toContain("Internacional");
    expect(menu?.textContent).toContain("A definir");
    expect(menu?.textContent).toContain("Importado");

    const option = menuOptions(wrapper, "origin-select").find(
      (item) => item.text() === "Internacional",
    );
    expect(option).toBeTruthy();
    await option!.trigger("click");

    await wrapper.get("form").trigger("submit");
    expect(patch).toHaveBeenCalledWith(
      "/equipments/eq-1",
      expect.objectContaining({ origin: "Internacional" }),
    );
  });

  it("equipamento novo parte de A definir, sem opção livre", async () => {
    const { wrapper } = await mountForm(null);

    expect(shownValue(wrapper, "origin-select")).toBe("A definir");

    await openMenu(wrapper, "origin-select");
    const menu = menuElement(wrapper, "origin-select");
    expect(menu?.textContent).toContain("Nacional");
    expect(menu?.textContent).toContain("Internacional");
    expect(menu?.textContent).toContain("A definir");
  });

  it("CAPEX e valor total usam moeda brasileira e enviam decimais", async () => {
    const current = { ...equipment(), capexEstimated: "483600.00" };
    const { wrapper, patch } = await mountForm(current);

    const capex = wrapper.get("[data-testid='capex-input']");
    const projectTotal = wrapper.get("[data-testid='project-total-input']");
    expect((capex.element as HTMLInputElement).value).toContain("483.600,00");
    expect((projectTotal.element as HTMLInputElement).value).toBe("");

    await capex.setValue("R$ 1.234,56");
    await projectTotal.setValue("2.500,00");
    await wrapper.get("form").trigger("submit");

    expect(patch).toHaveBeenCalledWith(
      "/equipments/eq-1",
      expect.objectContaining({
        capexEstimated: 1234.56,
        projectTotalValue: 2500,
      }),
    );
  });
});
