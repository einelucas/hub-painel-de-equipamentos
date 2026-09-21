import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import EquipmentStageForm from "~/components/equipment/EquipmentStageForm.vue";
import EquipmentWorkflowStepper from "~/components/equipment/EquipmentWorkflowStepper.vue";
import ProcessSummary from "~/components/equipment/ProcessSummary.vue";
import WorkflowRequirements from "~/components/equipment/WorkflowRequirements.vue";
import type { EquipmentProcesses, TransitionOption } from "~/types/equipment";

const processes = {
  negotiation: { id: null, equipmentId: "eq-1", equalized: false, negotiatedAt: null },
  legal: {
    id: null,
    equipmentId: "eq-1",
    openedAt: null,
    ticketNumber: null,
    draftPrepared: false,
    draftApproved: false,
  },
  contract: {
    id: null,
    equipmentId: "eq-1",
    contractNumber: "CT-0001",
    executedAt: "2026-03-01",
    deliveryAt: null,
  },
  purchaseRequest: {
    id: null,
    equipmentId: "eq-1",
    kind: null,
    requestNumber: null,
    requestedAt: null,
  },
  purchaseOrder: {
    id: null,
    equipmentId: "eq-1",
    orderNumber: null,
    orderedAt: null,
    amount: null,
  },
} satisfies EquipmentProcesses;

const blockedOption = {
  targetStage: 6,
  targetStageLabel: "SC ou OCI",
  kind: "advance",
  canExecute: false,
  requiresReason: false,
  blockedReason: null,
  requirements: [
    {
      code: "contract_number_required",
      field: "contract.contractNumber",
      message: "Informe o número do contrato.",
      satisfied: true,
    },
    {
      code: "contract_executed_at_required",
      field: "contract.executedAt",
      message: "Informe a data de escrituração do contrato.",
      satisfied: false,
    },
  ],
  satisfiedRequirements: [],
  missingRequirements: [],
} satisfies TransitionOption;

describe("EquipmentWorkflowStepper", () => {
  it("renderiza as nove etapas e destaca a atual", () => {
    const wrapper = mount(EquipmentWorkflowStepper, { props: { currentStage: 3 } });
    const steps = wrapper.findAll("[data-state]");
    expect(steps).toHaveLength(9);
    expect(steps[3]!.attributes("data-state")).toBe("current");
    expect(steps[3]!.attributes("aria-current")).toBe("step");
    expect(steps[0]!.attributes("data-state")).toBe("done");
    expect(wrapper.text()).toContain("Abertura do chamado");
  });

  it("não oferece nenhum controle clicável para mudar de etapa", () => {
    const wrapper = mount(EquipmentWorkflowStepper, { props: { currentStage: 2 } });
    expect(wrapper.findAll("button")).toHaveLength(0);
    expect(wrapper.findAll("a")).toHaveLength(0);
  });
});

describe("WorkflowRequirements", () => {
  it("lista requisitos atendidos e pendentes vindos do backend", () => {
    const wrapper = mount(WorkflowRequirements, { props: { option: blockedOption } });
    expect(wrapper.text()).toContain("6 · SC ou OCI");
    const pending = wrapper.get("[data-testid='requirement-contract_executed_at_required']");
    const done = wrapper.get("[data-testid='requirement-contract_number_required']");
    expect(pending.classes()).not.toContain("requirement--done");
    expect(done.classes()).toContain("requirement--done");
  });

  it("mostra o motivo do bloqueio quando o perfil não pode avançar", () => {
    const wrapper = mount(WorkflowRequirements, {
      props: {
        option: { ...blockedOption, blockedReason: "Seu perfil não tem permissão para avançar etapas." },
      },
    });
    expect(wrapper.text()).toContain("não tem permissão");
  });
});

describe("EquipmentStageForm", () => {
  it("apresenta o formulário da etapa atual preenchido com os dados do processo", () => {
    const wrapper = mount(EquipmentStageForm, {
      props: { stage: 5, processes, editable: true, saving: false },
    });
    const inputs = wrapper.findAll("input");
    expect((inputs[0]!.element as HTMLInputElement).value).toBe("CT-0001");
    expect((inputs[1]!.element as HTMLInputElement).value).toBe("2026-03-01");
  });

  it("emite apenas o salvamento do processo, sem pedir avanço de etapa", async () => {
    const wrapper = mount(EquipmentStageForm, {
      props: { stage: 1, processes, editable: true, saving: false },
    });
    await wrapper.get("input[type='checkbox']").setValue(true);
    await wrapper.get("form").trigger("submit");

    const emitted = wrapper.emitted("save");
    expect(emitted).toHaveLength(1);
    expect(emitted![0]).toEqual(["negotiation", { equalized: true, negotiatedAt: null }]);
    expect(wrapper.emitted("advance")).toBeUndefined();
    expect(wrapper.emitted("transition")).toBeUndefined();
  });

  it("bloqueia a edição de quem não tem permissão de escrita", () => {
    const wrapper = mount(EquipmentStageForm, {
      props: { stage: 1, processes, editable: false, saving: false },
    });
    expect(wrapper.get("fieldset").attributes("disabled")).toBeDefined();
    expect(wrapper.find("[data-testid='save-process']").exists()).toBe(false);
  });

  it("mostra a chamada para iniciar a negociação na etapa 0 e leitura na etapa 8", () => {
    const start = mount(EquipmentStageForm, {
      props: { stage: 0, processes, editable: true, saving: false },
    });
    const done = mount(EquipmentStageForm, {
      props: { stage: 8, processes, editable: true, saving: false },
    });
    expect(start.get("[data-testid='stage-form-intro']").text()).toContain("Inicie a negociação");
    expect(done.get("[data-testid='stage-form-done']").text()).toContain("Processo concluído");
  });
});

describe("ProcessSummary (GAP-008: edição independente da etapa atual)", () => {
  it("não mostra nenhum botão Editar para quem não tem process:write", () => {
    const wrapper = mount(ProcessSummary, {
      props: { processes, editable: false, saving: false },
    });
    expect(wrapper.findAll("button").filter((btn) => btn.text() === "Editar")).toHaveLength(0);
  });

  it("mostra Editar nos 5 blocos quando editable, independente de etapa (sem prop stage)", () => {
    const wrapper = mount(ProcessSummary, {
      props: { processes, editable: true, saving: false },
    });
    expect(wrapper.findAll("button").filter((btn) => btn.text() === "Editar")).toHaveLength(5);
  });

  it("editar e salvar o bloco SC/OCI emite só esse recurso, sem tocar em current_stage", async () => {
    const wrapper = mount(ProcessSummary, {
      props: { processes, editable: true, saving: false },
    });
    await wrapper.get("[data-testid='edit-purchase-request']").trigger("click");
    const form = wrapper.get("[data-testid='form-purchase-request']");
    await form.get("select").setValue("OCI");
    await form.get("input[maxlength='80']").setValue("OCI-9999");
    await form.trigger("submit");

    const emitted = wrapper.emitted("save");
    expect(emitted).toHaveLength(1);
    expect(emitted![0]).toEqual([
      "purchase-request",
      { kind: "OCI", requestNumber: "OCI-9999", requestedAt: null },
    ]);
  });

  it("cancelar a edição não emite nada e volta ao modo leitura", async () => {
    const wrapper = mount(ProcessSummary, {
      props: { processes, editable: true, saving: false },
    });
    await wrapper.get("[data-testid='edit-contract']").trigger("click");
    expect(wrapper.find("[data-testid='form-contract']").exists()).toBe(true);
    await wrapper.get("[data-testid='form-contract'] button[type='button']").trigger("click");
    expect(wrapper.emitted("save")).toBeUndefined();
    expect(wrapper.find("[data-testid='form-contract']").exists()).toBe(false);
  });
});
