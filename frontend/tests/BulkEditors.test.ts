import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import { VCheckbox, VSelect, VTextField } from "vuetify/components";
import ComponentBulkEditor from "~/components/equipment/ComponentBulkEditor.vue";
import EquipmentBulkEditor from "~/components/equipment/EquipmentBulkEditor.vue";
import SearchableMultiSelect from "~/components/ui/SearchableMultiSelect.vue";
import SearchableSelect from "~/components/ui/SearchableSelect.vue";
import { useConfirm } from "~/composables/useConfirm";
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
    workPackageOptions: [] as { id: string; label: string }[],
  };
}

const stubs = {
  BulkEditReviewDialog: true,
  NuxtLink: { template: "<a><slot /></a>" },
};

afterEach(() => {
  useConfirm().cancel();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("EquipmentBulkEditor", () => {
  it("usa os controles Vuetify padronizados nas células editáveis", () => {
    vi.stubGlobal("useApi", () => ({ get: vi.fn(), post: vi.fn() }));
    const wrapper = mount(EquipmentBulkEditor, {
      props: editorProps([
        equipment("eq-1", "Equipamento A", "2026-11-12T10:00:00"),
      ]),
      global: { stubs },
    });

    expect(wrapper.findComponent(VCheckbox).exists()).toBe(true);
    expect(wrapper.findAllComponents(SearchableSelect).length).toBeGreaterThan(0);
    expect(wrapper.findAllComponents(VTextField).length).toBeGreaterThan(0);
    expect(wrapper.find("select").exists()).toBe(false);
    expect(wrapper.findAllComponents(SearchableSelect)
      .every((select) => select.props("placeholder") === "Digite para buscar")).toBe(true);
    wrapper.unmount();
  });

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
    await massPanel.findAllComponents(VSelect)[0]?.vm.$emit("update:modelValue", "origin");
    await wrapper.vm.$nextTick();
    await massPanel.get(".mass-value").findComponent(VTextField).get("input").setValue("Coletivo");
    await massPanel.findAll("button").find((button) =>
      button.text().includes("Aplicar ao rascunho"))?.trigger("click");
    await wrapper.findAll("button").find((button) =>
      button.text().includes("Revisar alterações"))?.trigger("click");
    await flushPromises();

    const body = post.mock.calls[0]?.[1] as { items: { equipmentId: string }[] };
    expect(body.items.map((item) => item.equipmentId).sort()).toEqual(["eq-1", "eq-2"]);
    wrapper.unmount();
  });

  it("permite selecionar e enviar várias Work Packages na mesma linha", async () => {
    const post = vi.fn().mockResolvedValue({
      previewToken: "preview-token-1234",
      requestedCount: 1,
      changedCount: 1,
      skippedCount: 0,
      diffs: [],
      errors: [],
    });
    vi.stubGlobal("useApi", () => ({ get: vi.fn(), post }));
    const props = editorProps([
      equipment("eq-1", "Equipamento A", "2026-11-12T10:00:00"),
    ]);
    props.workPackageOptions = [
      { id: "wp-1", label: "CAL003" },
      { id: "wp-2", label: "ELT002" },
    ];
    const wrapper = mount(EquipmentBulkEditor, {
      props,
      global: { stubs },
    });

    await wrapper.findComponent(SearchableMultiSelect).vm.$emit(
      "update:modelValue",
      ["wp-1", "wp-2"],
    );
    await wrapper.findAll("button").find((button) =>
      button.text().includes("Revisar alterações"))?.trigger("click");
    await flushPromises();

    expect(post.mock.calls[0]?.[1]).toEqual({
      projectContextId: "ctx-1",
      items: [{
        equipmentId: "eq-1",
        expectedUpdatedAt: "2026-11-12T10:00:00",
        changes: [{
          field: "workPackageIds",
          operation: "REPLACE",
          value: ["wp-1", "wp-2"],
        }],
      }],
    });
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

    expect(wrapper.findComponent(VCheckbox).exists()).toBe(true);
    expect(wrapper.findAllComponents(VTextField).length).toBeGreaterThan(0);
    expect(wrapper.find("select").exists()).toBe(false);
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

  it("confirma o descarte em popup Vuetify antes de sair", async () => {
    vi.stubGlobal("useApi", () => ({ post: vi.fn() }));
    const wrapper = mount(ComponentBulkEditor, {
      props: { equipmentId: "eq-1", components: [component("comp-1", "Motor")] },
      global: { stubs },
    });

    await wrapper.get('input[aria-label="TAG: Motor"]').setValue("TAG-002");
    await wrapper.findAll("button").find((button) =>
      button.text().includes("Sair da edição"))?.trigger("click");

    expect(useConfirm().state.open).toBe(true);
    expect(useConfirm().state.title).toBe("Descartar alterações?");
    expect(useConfirm().state.confirmLabel).toBe("Descartar");
    expect(wrapper.emitted("exit")).toBeUndefined();

    useConfirm().accept();
    await flushPromises();
    expect(wrapper.emitted("exit")).toHaveLength(1);
    wrapper.unmount();
  });
});
