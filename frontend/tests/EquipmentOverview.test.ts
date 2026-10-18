import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import EquipmentOverview from "~/components/equipment/EquipmentOverview.vue";
import type { Equipment } from "~/types/equipment";

const equipment = {
  id: "eq-1",
  name: "Turbina",
  origin: null,
  startupAt: null,
  criticality: null,
  currentStage: 0,
  stageName: "Nova demanda",
  capexEstimated: null,
  unit: { id: "u1", name: "Nova Mutum" },
  projectContext: { id: "c1", code: "C4", name: "Caldeira 4" },
  eapNode: {
    id: "e1",
    code: "04.A",
    name: "Casa de Força",
    level: "AREA",
    active: true,
  },
  area: null,
  discipline: null,
  workPackage: null,
  workPackages: [],
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
  createdAt: "2026-10-07T00:00:00Z",
  updatedAt: "2026-10-07T00:00:00Z",
} satisfies Equipment;

function overview(overrides: Partial<Equipment> = {}) {
  return mount(EquipmentOverview, {
    props: {
      equipment: { ...equipment, ...overrides },
      currentStage: 0,
      currentStageLabel: "Nova demanda",
      operationalStatus: "ACTIVE",
      lastOperationalEvent: null,
      nextStageBlocked: false,
      canEdit: false,
    },
    global: {
      stubs: { EquipmentWorkflowStepper: true },
    },
  });
}

/** Valor de um campo do resumo, localizado pelo rótulo visível. */
function fieldText(wrapper: ReturnType<typeof mount>, label: string): string {
  const field = wrapper
    .findAll(".detail-field")
    .find((item) => item.get("span").text() === label);
  if (!field) throw new Error(`Campo "${label}" não está no resumo.`);
  return field.get("strong").text();
}

describe("EquipmentOverview", () => {
  it("mostra a localização canônica da Árvore EAP no resumo", () => {
    const wrapper = mount(EquipmentOverview, {
      props: {
        equipment,
        currentStage: 0,
        currentStageLabel: "Nova demanda",
        operationalStatus: "ACTIVE",
        lastOperationalEvent: null,
        nextStageBlocked: false,
        canEdit: false,
      },
      global: {
        stubs: { EquipmentWorkflowStepper: true },
      },
    });

    expect(wrapper.get("[data-testid='equipment-location']").text()).toBe(
      "04.A · Casa de Força",
    );
  });

  it("chama a obra de Obra e mostra a Origem no resumo", () => {
    const wrapper = overview({ origin: "Nacional" });

    expect(fieldText(wrapper, "Obra")).toBe("C4 · Caldeira 4");
    expect(fieldText(wrapper, "Origem")).toBe("Nacional");
    expect(wrapper.text()).not.toContain("Contexto");
  });

  it("mostra — na Origem quando o equipamento não tem o dado", () => {
    expect(fieldText(overview({ origin: null }), "Origem")).toBe("—");
  });

  it("preserva a sequência original do resumo, com Origem no fim", () => {
    const labels = overview()
      .findAll(".detail-field")
      .map((item) => item.get("span").text());

    expect(labels).toEqual([
      "Unidade",
      "Obra",
      "Área",
      "Disciplina",
      "Work Packages",
      "Responsável",
      "Fornecedor",
      "Etapa atual",
      "Estado operacional",
      "Startup",
      "Criticidade",
      "CAPEX estimado",
      "Valor total do projeto",
      "Entrega contratual",
      "Origem",
    ]);
  });
});
