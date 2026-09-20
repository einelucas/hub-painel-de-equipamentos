import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import EquipmentTable from "~/components/equipment/EquipmentTable.vue";
import type { Equipment } from "~/types/equipment";

const equipment = {
  id: "eq-1",
  name: "Bomba principal",
  origin: null,
  startupAt: null,
  criticality: "Alta",
  currentStage: 1,
  stageName: "Negociação",
  capexEstimated: null,
  projectContext: { id: "ctx", code: "C2", name: "Contexto C2" },
  unit: { id: "unit", code: "LEM", name: "Lucas do Rio Verde" },
  discipline: null,
  area: null,
  workPackage: null,
  responsibleUser: null,
  componentsCount: 2,
  createdAt: "2026-09-20T00:00:00",
  updatedAt: "2026-09-20T00:00:00",
} satisfies Equipment;

const passthrough = { template: "<div><slot /></div>" };

describe("EquipmentTable", () => {
  it("renderiza o estado vazio", () => {
    const wrapper = mount(EquipmentTable, { props: { equipments: [] } });
    expect(wrapper.get("[data-testid='equipment-empty']").text()).toContain("Nenhum equipamento");
  });

  it("renderiza a tabela e o link de detalhe", () => {
    const wrapper = mount(EquipmentTable, {
      props: { equipments: [equipment] },
      global: {
        stubs: {
          Table: passthrough,
          TableHeader: passthrough,
          TableRow: passthrough,
          TableHead: passthrough,
          TableBody: passthrough,
          TableCell: passthrough,
          NuxtLink: { props: ["to"], template: "<a :href='to'><slot /></a>" },
        },
      },
    });
    expect(wrapper.text()).toContain("Bomba principal");
    expect(wrapper.text()).toContain("1 · Negociação");
    expect(wrapper.get("a").attributes("href")).toBe("/equipamentos/eq-1");
  });
});
