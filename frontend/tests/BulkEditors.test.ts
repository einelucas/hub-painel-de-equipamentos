import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import ComponentBulkEditor from "~/components/equipment/ComponentBulkEditor.vue";
import EquipmentBulkEditor from "~/components/equipment/EquipmentBulkEditor.vue";
import type { Equipment, EquipmentComponent } from "~/types/equipment";

function equipment(id: string, name: string, updatedAt: string): Equipment {
  return {
    id,
    name,
    origin: null,
    startupAt: null,
    criticality: null,
    currentStage: 0,
    stageName: "Nova demanda",
    capexEstimated: null,
    projectContext: { id: "ctx-1", name: "Obra Teste" },
    unit: { id: "unit-1", name: "Unidade Teste" },
    discipline: null,
    eapNode: null,
    area: null,
    supplier: null,
    operationalStatus: "ACTIVE",
    projectTotalValue: null,
    contractualDeliveryStart: null,
    contractualDeliveryEnd: null,
    workPackage: null,
    workPackages: [],
    responsibleUser: null,
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
    createdAt: updatedAt,
    updatedAt,
  };
}

function component(id: string, name: string): EquipmentComponent {
  return {
    id,
    equipmentId: "eq-1",
    name,
    tag: null,
    sector: null,
    startupAt: null,
    leadTimeDays: null,
    preStartDays: null,
    contractDeliveryAt: null,
    freightDays: null,
    calculated: {
      deliveryDeadline: null,
      availableForCollection: null,
      contractOrderDeadline: null,
      negotiationDeadline: null,
      negotiationDaysRemaining: null,
      deliveryMarginDays: null,
    },
    createdAt: "2026-11-12T10:00:00",
    updatedAt: "2026-11-12T10:00:00",
  };
}

function editorProps(equipments: Equipment[]) {
  return {
    equipments,
    projectContextId: "ctx-1",
    filters: { stage: 0 },
    total: 2,
    disciplineOptions: [],
    responsibleOptions: [],
    eapOptions: [],
    criticalityOptions: [],
    workPackageOptions: [],
  };
}

const stubs = {
  BulkEditReviewDialog: true,
  NuxtLink: { template: "<a><slot /></a>" },
};

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("EquipmentBulkEditor", () => {
  it("preserva rascunhos ao trocar de página e envia as duas versões originais", async () => {
    const post = vi.fn().mockResolvedValue({
      previewToken: "preview-token-1234",
      requestedCount: 2,
      changedCount: 2,
      skippedCount: 0,
      diffs: [],
      errors: [],
    });
    vi.stubGlobal("useApi", () => ({ get: vi.fn(), post }));
    const first = equipment("eq-1", "Equipamento A", "2026-11-12T10:00:00");
    const second = equipment("eq-2", "Equipamento B", "2026-11-12T11:00:00");
    const wrapper = mount(EquipmentBulkEditor, {
      props: editorProps([first]),
      global: { stubs },
    });

    await wrapper.get('input[aria-label="Origem: Equipamento A"]').setValue("Manual A");
    await wrapper.setProps({ equipments: [second] });
    await wrapper.get('input[aria-label="Origem: Equipamento B"]').setValue("Manual B");
    await wrapper.findAll("button").find((button) =>
      button.text().includes("Revisar alterações"))?.trigger("click");
    await flushPromises();

    expect(post).toHaveBeenCalledTimes(1);
    expect(post.mock.calls[0]?.[0]).toBe("/equipments/bulk/preview");
    expect(post.mock.calls[0]?.[1]).toEqual({
      projectContextId: "ctx-1",
      items: [
        {
          equipmentId: "eq-1",
          expectedUpdatedAt: "2026-11-12T10:00:00",
          changes: [{ field: "origin", operation: "SET", value: "Manual A" }],
        },
        {
          equipmentId: "eq-2",
          expectedUpdatedAt: "2026-11-12T11:00:00",
          changes: [{ field: "origin", operation: "SET", value: "Manual B" }],
        },
      ],
    });
    wrapper.unmount();
  });

  it("materializa todos os filtrados no servidor, inclusive fora da página atual", async () => {
    const get = vi.fn().mockResolvedValue({
      total: 2,
      items: [
        { equipmentId: "eq-1", name: "Equipamento A", expectedUpdatedAt: "2026-11-12T10:00:00" },
        { equipmentId: "eq-2", name: "Equipamento B", expectedUpdatedAt: "2026-11-12T11:00:00" },
      ],
    });
    const post = vi.fn().mockResolvedValue({
      previewToken: "preview-token-1234",
      requestedCount: 2,
      changedCount: 2,
      skippedCount: 0,
      diffs: [],
      errors: [],
    });
    vi.stubGlobal("useApi", () => ({ get, post }));
    const wrapper = mount(EquipmentBulkEditor, {
      props: editorProps([
        equipment("eq-1", "Equipamento A", "2026-11-12T10:00:00"),
      ]),
      global: { stubs },
    });

    await wrapper.findAll("button").find((button) =>
      button.text().includes("Todos os filtrados"))?.trigger("click");
    await flushPromises();
    expect(get).toHaveBeenCalledWith(
      "/equipments/bulk/selection",
      { stage: 0, projectContextId: "ctx-1" },
      { force: true },
    );
    expect(wrapper.text()).toContain("2 linha(s) selecionada(s)");

    const massPanel = wrapper.get(".mass-panel");
    await massPanel.get("select").setValue("origin");
    await massPanel.get('input[type="text"]').setValue("Coletivo");
    await massPanel.findAll("button").find((button) =>
      button.text().includes("Aplicar ao rascunho"))?.trigger("click");
    await wrapper.findAll("button").find((button) =>
      button.text().includes("Revisar alterações"))?.trigger("click");
    await flushPromises();

    const body = post.mock.calls[0]?.[1] as { items: { equipmentId: string }[] };
    expect(body.items.map((item) => item.equipmentId).sort()).toEqual(["eq-1", "eq-2"]);
    wrapper.unmount();
  });
});

describe("ComponentBulkEditor", () => {
  it("permite TAG somente por célula e mantém entrega contratual fora do modo tabela", async () => {
    const post = vi.fn().mockResolvedValue({
      previewToken: "preview-token-1234",
      requestedCount: 1,
      changedCount: 1,
      skippedCount: 0,
      diffs: [],
      errors: [],
    });
    vi.stubGlobal("useApi", () => ({ post }));
    const wrapper = mount(ComponentBulkEditor, {
      props: { equipmentId: "eq-1", components: [component("comp-1", "Motor")] },
      global: { stubs },
    });

    expect(wrapper.text()).not.toContain("Entrega contratual");
    await wrapper.get('input[aria-label="Selecionar Motor"]').setValue(true);
    expect(wrapper.get(".mass-panel").text()).not.toContain("TAG");
    await wrapper.get('input[aria-label="TAG: Motor"]').setValue("TAG-001");
    await wrapper.findAll("button").find((button) =>
      button.text().includes("Revisar alterações"))?.trigger("click");
    await flushPromises();

    expect(post.mock.calls[0]?.[1]).toEqual({
      items: [{
        componentId: "comp-1",
        expectedUpdatedAt: "2026-11-12T10:00:00",
        changes: [{ field: "tag", operation: "SET", value: "TAG-001" }],
      }],
    });
    wrapper.unmount();
  });
});
