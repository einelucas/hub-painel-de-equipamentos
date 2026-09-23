import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import EquipmentStageForm from "~/components/equipment/EquipmentStageForm.vue";
import EquipmentWorkflowStepper from "~/components/equipment/EquipmentWorkflowStepper.vue";
import ProcessSummary from "~/components/equipment/ProcessSummary.vue";
import WorkflowRequirements from "~/components/equipment/WorkflowRequirements.vue";
import type { EquipmentProcesses, TransitionOption } from "~/types/equipment";

vi.stubGlobal("useAuthStore", () => ({ can: () => true }));
vi.stubGlobal("useApi", () => ({
  post: vi.fn().mockResolvedValue({}),
  get: vi.fn().mockResolvedValue({}),
  patch: vi.fn().mockResolvedValue({}),
  delete: vi.fn().mockResolvedValue({}),
}));
vi.stubGlobal("useRoute", () => ({ params: { id: "eq-1" } }));

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
  contracts: [
    {
      id: "ct-1",
      equipmentId: "eq-1",
      contractNumber: "CT-0001",
      executedAt: "2026-03-01",
      file: null,
      createdAt: "2026-03-01T00:00:00",
      updatedAt: "2026-03-01T00:00:00",
    },
  ],
  purchaseRequests: [],
  purchaseOrders: [],
} satisfies EquipmentProcesses;

const blockedOption = {
  targetStage: 6,
  targetStageLabel: "SC ou OCI",
  kind: "advance",
  canExecute: false,
  requiresReason: false,
  blockedReason: null,
  requirementGroups: [
    {
      code: "NEGOTIATION_EQUALIZATION",
      label: "Equalização da negociação",
      status: "SATISFIED",
      waivable: true,
      fields: ["negotiation.equalized"],
      message: "Confirme a equalização da negociação.",
      waiver: null,
    },
    {
      code: "CONTRACT",
      label: "Contrato",
      status: "MISSING",
      waivable: true,
      fields: ["contract.contractNumber", "contract.executedAt", "contract.file"],
      message: "Informe a data de escrituração do contrato.",
      waiver: null,
    },
  ],
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
  it("lista requisitos atendidos e pendentes por grupo, vindos do backend", () => {
    const wrapper = mount(WorkflowRequirements, { props: { option: blockedOption } });
    expect(wrapper.text()).toContain("6 · SC ou OCI");
    const pending = wrapper.get("[data-testid='requirement-CONTRACT']");
    const done = wrapper.get("[data-testid='requirement-NEGOTIATION_EQUALIZATION']");
    expect(pending.classes()).not.toContain("requirement--done");
    expect(done.classes()).toContain("requirement--done");
    // Etapa 7.1: a ação "Não possui" fica junto de onde o dado é
    // registrado (RequirementWaiverBanner, nas listas/formulário da fase),
    // não neste painel — aqui só um aviso apontando para lá.
    expect(wrapper.text()).toContain("Não possui");
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
      props: { stage: 1, processes, editable: true, saving: false, equipmentId: "eq-1" },
    });
    expect(wrapper.find("input[type='checkbox']").exists()).toBe(true);
  });

  it("emite apenas o salvamento do processo, sem pedir avanço de etapa", async () => {
    const wrapper = mount(EquipmentStageForm, {
      props: { stage: 1, processes, editable: true, saving: false, equipmentId: "eq-1" },
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
      props: { stage: 1, processes, editable: false, saving: false, equipmentId: "eq-1" },
    });
    expect(wrapper.get("fieldset").attributes("disabled")).toBeDefined();
    expect(wrapper.find("[data-testid='save-process']").exists()).toBe(false);
  });

  it("mostra a chamada para iniciar a negociação na etapa 0 e leitura na etapa 8", () => {
    const start = mount(EquipmentStageForm, {
      props: { stage: 0, processes, editable: true, saving: false, equipmentId: "eq-1" },
    });
    const done = mount(EquipmentStageForm, {
      props: { stage: 8, processes, editable: true, saving: false, equipmentId: "eq-1" },
    });
    expect(start.get("[data-testid='stage-form-intro']").text()).toContain("Inicie a negociação");
    expect(done.get("[data-testid='stage-form-done']").text()).toContain("Processo concluído");
  });

  it("etapas 5-7 apontam para as listas dedicadas (Contratos/SC-OCI/OC), sem formulário inline", () => {
    const wrapper = mount(EquipmentStageForm, {
      props: { stage: 5, processes, editable: true, saving: false, equipmentId: "eq-1" },
    });
    expect(wrapper.get("[data-testid='stage-form-list']").text()).toContain("Contratos");
    expect(wrapper.find("form").exists()).toBe(false);
  });
});

describe("ProcessSummary (GAP-008: edição independente da etapa atual)", () => {
  it("não mostra nenhum botão Editar para quem não tem process:write", () => {
    const wrapper = mount(ProcessSummary, {
      props: { processes, editable: false, saving: false },
    });
    expect(wrapper.findAll("button").filter((btn) => btn.text() === "Editar")).toHaveLength(0);
  });

  it("mostra Editar nos 2 blocos (negociação/jurídico) quando editable — contrato/SC-OCI/OC viraram listas próprias", () => {
    const wrapper = mount(ProcessSummary, {
      props: { processes, editable: true, saving: false },
    });
    expect(wrapper.findAll("button").filter((btn) => btn.text() === "Editar")).toHaveLength(2);
  });

  it("editar e salvar o bloco jurídico emite só esse recurso, sem tocar em current_stage", async () => {
    const wrapper = mount(ProcessSummary, {
      props: { processes, editable: true, saving: false },
    });
    await wrapper.get("[data-testid='edit-legal']").trigger("click");
    const form = wrapper.get("[data-testid='form-legal']");
    await form.get("input[maxlength='80']").setValue("TICKET-9999");
    await form.trigger("submit");

    const emitted = wrapper.emitted("save");
    expect(emitted).toHaveLength(1);
    expect(emitted![0]).toEqual([
      "legal",
      { openedAt: null, ticketNumber: "TICKET-9999", draftPrepared: false, draftApproved: false },
    ]);
  });

  it("cancelar a edição não emite nada e volta ao modo leitura", async () => {
    const wrapper = mount(ProcessSummary, {
      props: { processes, editable: true, saving: false },
    });
    await wrapper.get("[data-testid='edit-negotiation']").trigger("click");
    expect(wrapper.find("[data-testid='form-negotiation']").exists()).toBe(true);
    await wrapper.get("[data-testid='form-negotiation'] button[type='button']").trigger("click");
    expect(wrapper.emitted("save")).toBeUndefined();
    expect(wrapper.find("[data-testid='form-negotiation']").exists()).toBe(false);
  });
});
