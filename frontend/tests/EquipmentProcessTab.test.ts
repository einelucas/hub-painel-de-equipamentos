import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import EquipmentProcessTab from "~/components/equipment/EquipmentProcessTab.vue";
import type { EquipmentProcesses, RequirementGroup, TransitionOption } from "~/types/equipment";

/**
 * EquipmentProcessTab só compõe componentes já existentes e testados
 * isoladamente (EquipmentStageForm, WorkflowRequirements, ProcessSummary,
 * as 3 listas). Aqui testamos a FIAÇÃO — props/eventos certos chegando em
 * cada filho, avançar etapa, recarregar — não o comportamento interno de
 * cada um (que já tem seus próprios testes). Por isso os filhos são
 * substituídos por stubs mínimos que expõem o que receberam e permitem
 * disparar os eventos que o componente precisa tratar.
 */
const EquipmentStageFormStub = {
  props: ["stage", "processes", "editable", "saving", "equipmentId", "requirementGroup"],
  emits: ["save", "changed"],
  template: `<div data-testid="stub-stage-form">{{ requirementGroup?.code ?? 'none' }}
    <button data-testid="stub-save" type="button" @click="$emit('save', 'negotiation', { equalized: true, negotiatedAt: null })">save</button>
    <button data-testid="stub-stage-changed" type="button" @click="$emit('changed')">changed</button>
  </div>`,
};
const WorkflowRequirementsStub = {
  props: ["option"],
  template: `<div data-testid="stub-requirements">{{ option.targetStageLabel }}</div>`,
};
const ProcessSummaryStub = {
  props: ["processes", "editable", "saving"],
  emits: ["save"],
  template: `<div data-testid="stub-summary">
    <button data-testid="stub-summary-save" type="button" @click="$emit('save', 'legal', { openedAt: null, ticketNumber: 'T-1', draftPrepared: false, draftApproved: false })">save</button>
  </div>`,
};
const ContractsStub = {
  props: ["equipmentId", "contracts", "editable", "requirementGroup", "requirementStage", "requirementWaiver"],
  emits: ["changed"],
  template: `<div data-testid="stub-contracts">{{ requirementGroup?.code ?? 'none' }}
    <button data-testid="stub-contracts-changed" type="button" @click="$emit('changed')">changed</button>
  </div>`,
};
const PurchaseRequestsStub = {
  props: ["equipmentId", "items", "editable", "requirementGroup", "requirementStage", "requirementWaiver"],
  emits: ["changed"],
  template: `<div data-testid="stub-purchase-requests">{{ requirementGroup?.code ?? 'none' }}
    <button data-testid="stub-pr-changed" type="button" @click="$emit('changed')">changed</button>
  </div>`,
};
const PurchaseOrdersStub = {
  props: ["equipmentId", "items", "editable"],
  emits: ["changed"],
  template: `<div data-testid="stub-purchase-orders">
    <button data-testid="stub-po-changed" type="button" @click="$emit('changed')">changed</button>
  </div>`,
};

const globalStubs = {
  components: {
    EquipmentStageForm: EquipmentStageFormStub,
    WorkflowRequirements: WorkflowRequirementsStub,
    ProcessSummary: ProcessSummaryStub,
    EquipmentContractsList: ContractsStub,
    EquipmentPurchaseRequestsList: PurchaseRequestsStub,
    EquipmentPurchaseOrdersList: PurchaseOrdersStub,
  },
};

const processes: EquipmentProcesses = {
  negotiation: { id: null, equipmentId: "eq-1", equalized: false, negotiatedAt: null },
  legal: {
    id: null,
    equipmentId: "eq-1",
    openedAt: null,
    ticketNumber: null,
    draftPrepared: false,
    draftApproved: false,
  },
  contracts: [],
  purchaseRequests: [],
  purchaseOrders: [],
};

function group(code: string, status: RequirementGroup["status"] = "MISSING"): RequirementGroup {
  return { code, label: code, status, waivable: true, fields: [], message: "", waiver: null };
}

function advanceOption(overrides: Partial<TransitionOption> = {}): TransitionOption {
  return {
    targetStage: 6,
    targetStageLabel: "SC ou OCI",
    kind: "advance",
    canExecute: false,
    requiresReason: false,
    blockedReason: null,
    requirementGroups: [group("NEGOTIATION_EQUALIZATION"), group("CONTRACT"), group("PURCHASE_REQUEST")],
    ...overrides,
  };
}

function mountTab(propsOverrides: Partial<InstanceType<typeof EquipmentProcessTab>["$props"]> = {}) {
  const saveProcess = vi.fn().mockResolvedValue(true);
  const requestTransition = vi.fn().mockResolvedValue(true);
  const reloadProcess = vi.fn().mockResolvedValue(undefined);
  const activeWaiverFor = vi.fn().mockReturnValue(null);

  const wrapper = mount(EquipmentProcessTab, {
    props: {
      equipmentId: "eq-1",
      currentStage: 5,
      currentStageLabel: "Escrituração do contrato",
      canWriteProcess: true,
      loading: false,
      error: "",
      processes,
      advance: advanceOption(),
      advancing: false,
      saving: false,
      actionError: "",
      actionSuccess: "",
      saveProcess,
      requestTransition,
      reloadProcess,
      activeWaiverFor,
      ...propsOverrides,
    },
    global: globalStubs,
  });
  return { wrapper, saveProcess, requestTransition, reloadProcess, activeWaiverFor };
}

describe("EquipmentProcessTab", () => {
  it("carregando: mostra o estado de loading do workflow", () => {
    const { wrapper } = mountTab({ loading: true, processes: null, advance: null });
    expect(wrapper.text()).toContain("Carregando processo...");
    expect(wrapper.find("[data-testid='stub-stage-form']").exists()).toBe(false);
  });

  it("erro: mostra a mensagem e o botão de tentar novamente chama reloadProcess", async () => {
    const { wrapper, reloadProcess } = mountTab({
      error: "Falha ao buscar",
      processes: null,
      advance: null,
    });
    expect(wrapper.text()).toContain("Falha ao buscar");
    await wrapper.get("button").trigger("click");
    expect(reloadProcess).toHaveBeenCalledTimes(1);
  });

  it("repassa o grupo de requisito da fase atual (primeiro da lista) para EquipmentStageForm", () => {
    const { wrapper } = mountTab();
    expect(wrapper.get("[data-testid='stub-stage-form']").text()).toContain("NEGOTIATION_EQUALIZATION");
  });

  it("repassa CONTRACT/PURCHASE_REQUEST para as listas certas, por código", () => {
    const { wrapper } = mountTab();
    expect(wrapper.get("[data-testid='stub-contracts']").text()).toContain("CONTRACT");
    expect(wrapper.get("[data-testid='stub-purchase-requests']").text()).toContain("PURCHASE_REQUEST");
  });

  it("Salvar: @save do formulário da etapa chama saveProcess com o recurso e o payload", async () => {
    const { wrapper, saveProcess } = mountTab();
    await wrapper.get("[data-testid='stub-save']").trigger("click");
    expect(saveProcess).toHaveBeenCalledWith("negotiation", { equalized: true, negotiatedAt: null });
  });

  it("Salvar: @save do Processo completo (ProcessSummary) também usa saveProcess", async () => {
    const { wrapper, saveProcess } = mountTab();
    await wrapper.get("[data-testid='stub-summary-save']").trigger("click");
    expect(saveProcess).toHaveBeenCalledWith("legal", {
      openedAt: null,
      ticketNumber: "T-1",
      draftPrepared: false,
      draftApproved: false,
    });
  });

  it("Alterar lista: @changed do formulário e das 3 listas chama reloadProcess (não a página inteira)", async () => {
    const { wrapper, reloadProcess } = mountTab();
    await wrapper.get("[data-testid='stub-stage-changed']").trigger("click");
    await wrapper.get("[data-testid='stub-contracts-changed']").trigger("click");
    await wrapper.get("[data-testid='stub-pr-changed']").trigger("click");
    await wrapper.get("[data-testid='stub-po-changed']").trigger("click");
    expect(reloadProcess).toHaveBeenCalledTimes(4);
  });

  it("Avançar: botão desabilitado quando canExecute é false", () => {
    const { wrapper } = mountTab({ advance: advanceOption({ canExecute: false }) });
    expect(wrapper.get("[data-testid='advance-button']").attributes("disabled")).toBeDefined();
  });

  it("Avançar: clique com canExecute chama requestTransition com a fase de destino e emite 'advanced' em sucesso", async () => {
    const { wrapper, requestTransition } = mountTab({ advance: advanceOption({ canExecute: true, targetStage: 6 }) });
    await wrapper.get("[data-testid='advance-button']").trigger("click");

    expect(requestTransition).toHaveBeenCalledWith(6);
    expect(wrapper.emitted("advanced")).toHaveLength(1);
  });

  it("Avançar: se requestTransition falhar (retorno false), não emite 'advanced'", async () => {
    const { wrapper } = mountTab({
      advance: advanceOption({ canExecute: true }),
      requestTransition: vi.fn().mockResolvedValue(false),
    });
    await wrapper.get("[data-testid='advance-button']").trigger("click");
    expect(wrapper.emitted("advanced")).toBeUndefined();
  });

  it("Avançar: com processo concluído (advance null), mostra a mensagem final e não o botão", () => {
    const { wrapper } = mountTab({ advance: null });
    expect(wrapper.text()).toContain("Processo concluído — não há próxima etapa.");
    expect(wrapper.find("[data-testid='advance-button']").exists()).toBe(false);
  });

  it("mostra action-error e action-success vindos do workflow", () => {
    const withError = mountTab({ actionError: "Deu ruim" }).wrapper;
    expect(withError.get("[data-testid='action-error']").text()).toBe("Deu ruim");

    const withSuccess = mountTab({ actionSuccess: "Salvo!" }).wrapper;
    expect(withSuccess.get("[data-testid='action-success']").text()).toBe("Salvo!");
  });
});
