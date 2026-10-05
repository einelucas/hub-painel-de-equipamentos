import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import EquipmentReopenPanel from "~/components/equipment/EquipmentReopenPanel.vue";
import type { ReopenRequest } from "~/types/equipment";

/**
 * AppModal usa <Teleport to="body">, que complica a busca por elementos em
 * testes de montagem isolada. Como já é feito em EquipmentSuppliers.test.ts
 * e EquipmentOperationalActions.test.ts, substituímos por uma div simples
 * que ainda respeita `open`.
 */
const appModalStub = {
  props: ["open", "title"],
  template: "<div v-if=\"open\" class=\"modal-stub\"><p>{{ title }}</p><slot /></div>",
};

function pendingRequest(overrides: Partial<ReopenRequest> = {}): ReopenRequest {
  return {
    id: "reopen-1",
    equipmentId: "eq-1",
    sourceStage: 5,
    sourceStageLabel: "Escrituração do contrato",
    targetStage: 2,
    targetStageLabel: "Equalização",
    justification: "Fornecedor trocado, negociação precisa ser refeita.",
    status: "PENDING",
    requestedBy: { id: "u-1", name: "Analista Sintético A", email: "analistaA@example.com" },
    requestedAt: "2026-09-20T10:00:00",
    decidedBy: null,
    decidedAt: null,
    decisionNote: null,
    ...overrides,
  };
}

function mountPanel(
  props: Partial<{
    currentStage: number;
    isActive: boolean;
    canRequestReopen: boolean;
    canApproveReopen: boolean;
    pendingReopenRequest: ReopenRequest | null;
    busy: boolean;
    actionError: string;
    requestReopen: ReturnType<typeof vi.fn>;
    approveReopen: ReturnType<typeof vi.fn>;
    rejectReopen: ReturnType<typeof vi.fn>;
  }> = {},
) {
  const requestReopen = props.requestReopen ?? vi.fn().mockResolvedValue({});
  const approveReopen = props.approveReopen ?? vi.fn().mockResolvedValue({});
  const rejectReopen = props.rejectReopen ?? vi.fn().mockResolvedValue({});

  const wrapper = mount(EquipmentReopenPanel, {
    props: {
      currentStage: props.currentStage ?? 3,
      isActive: props.isActive ?? true,
      canRequestReopen: props.canRequestReopen ?? true,
      canApproveReopen: props.canApproveReopen ?? true,
      pendingReopenRequest: props.pendingReopenRequest ?? null,
      busy: props.busy ?? false,
      actionError: props.actionError ?? "",
      requestReopen,
      approveReopen,
      rejectReopen,
    },
    global: { stubs: { AppModal: appModalStub } },
  });
  return { wrapper, requestReopen, approveReopen, rejectReopen };
}

describe("EquipmentReopenPanel", () => {
  it("mostra 'Solicitar reabertura' quando permitido, ativo e há fase anterior", () => {
    const { wrapper } = mountPanel();
    expect(wrapper.find("[data-testid='request-reopen-button']").exists()).toBe(true);
  });

  it("esconde o botão sem permissão workflow:reopen_request", () => {
    const { wrapper } = mountPanel({ canRequestReopen: false });
    expect(wrapper.find("[data-testid='request-reopen-button']").exists()).toBe(false);
  });

  it("mostra aviso quando não há fase anterior para reabrir", () => {
    const { wrapper } = mountPanel({ currentStage: 0 });
    expect(wrapper.find("[data-testid='request-reopen-button']").exists()).toBe(false);
    expect(wrapper.text()).toContain("Não há fase anterior para reabrir");
  });

  it("mostra os dados da solicitação pendente", () => {
    const { wrapper } = mountPanel({ pendingReopenRequest: pendingRequest() });
    const text = wrapper.get("[data-testid='pending-reopen-request']").text();
    expect(text).toContain("2 · Equalização");
    expect(text).toContain("Analista Sintético A");
    expect(text).toContain("Fornecedor trocado, negociação precisa ser refeita.");
    expect(wrapper.find("[data-testid='request-reopen-button']").exists()).toBe(false);
  });

  it("esconde Aprovar/Rejeitar sem permissão workflow:reopen_approve", () => {
    const { wrapper } = mountPanel({ pendingReopenRequest: pendingRequest(), canApproveReopen: false });
    expect(wrapper.find("[data-testid='approve-reopen']").exists()).toBe(false);
    expect(wrapper.find("[data-testid='reject-reopen']").exists()).toBe(false);
  });

  it("Solicitar: preenche fase e justificativa, chama requestReopen e fecha o modal em sucesso", async () => {
    const { wrapper, requestReopen } = mountPanel({ currentStage: 5 });
    await wrapper.get("[data-testid='request-reopen-button']").trigger("click");
    expect(wrapper.find(".modal-stub").exists()).toBe(true);

    await wrapper.get("select").setValue("2");
    await wrapper.get("textarea").setValue("Precisa renegociar com o novo fornecedor.");
    await wrapper.get("form").trigger("submit");

    expect(requestReopen).toHaveBeenCalledWith(2, "Precisa renegociar com o novo fornecedor.");
    expect(wrapper.find(".modal-stub").exists()).toBe(false);
  });

  it("Solicitar: submit fica bloqueado sem fase ou sem justificativa", async () => {
    const { wrapper, requestReopen } = mountPanel({ currentStage: 5 });
    await wrapper.get("[data-testid='request-reopen-button']").trigger("click");

    expect(wrapper.get("button[type='submit']").attributes("disabled")).toBeDefined();

    await wrapper.get("select").setValue("2");
    expect(wrapper.get("button[type='submit']").attributes("disabled")).toBeDefined();

    await wrapper.get("textarea").setValue("Justificativa.");
    expect(wrapper.get("button[type='submit']").attributes("disabled")).toBeUndefined();
    expect(requestReopen).not.toHaveBeenCalled();
  });

  it("Solicitar: retorno null (erro) mantém o modal aberto", async () => {
    const { wrapper, requestReopen } = mountPanel({
      currentStage: 5,
      requestReopen: vi.fn().mockResolvedValue(null),
    });
    await wrapper.get("[data-testid='request-reopen-button']").trigger("click");
    await wrapper.get("select").setValue("2");
    await wrapper.get("textarea").setValue("Justificativa.");
    await wrapper.get("form").trigger("submit");

    expect(requestReopen).toHaveBeenCalled();
    expect(wrapper.find(".modal-stub").exists()).toBe(true);
  });

  it("Solicitar: cancelar no modal fecha sem chamar requestReopen", async () => {
    const { wrapper, requestReopen } = mountPanel({ currentStage: 5 });
    await wrapper.get("[data-testid='request-reopen-button']").trigger("click");
    await wrapper.get(".modal-stub form button[type='button']").trigger("click");

    expect(requestReopen).not.toHaveBeenCalled();
    expect(wrapper.find(".modal-stub").exists()).toBe(false);
  });

  it("Aprovar: chama approveReopen com o id da solicitação, fecha o modal e emite 'decided'", async () => {
    const { wrapper, approveReopen } = mountPanel({ pendingReopenRequest: pendingRequest() });
    await wrapper.get("[data-testid='approve-reopen']").trigger("click");
    expect(wrapper.get(".modal-stub p").text()).toBe("Aprovar reabertura");

    await wrapper.get("textarea").setValue("Ok, aprovado.");
    await wrapper.get("form").trigger("submit");

    expect(approveReopen).toHaveBeenCalledWith("reopen-1", "Ok, aprovado.");
    expect(wrapper.find(".modal-stub").exists()).toBe(false);
    expect(wrapper.emitted("decided")).toHaveLength(1);
  });

  it("Aprovar: nota é opcional", async () => {
    const { wrapper, approveReopen } = mountPanel({ pendingReopenRequest: pendingRequest() });
    await wrapper.get("[data-testid='approve-reopen']").trigger("click");
    await wrapper.get("form").trigger("submit");

    expect(approveReopen).toHaveBeenCalledWith("reopen-1", "");
  });

  it("Aprovar: retorno null (erro) mantém o modal aberto e não emite 'decided'", async () => {
    const { wrapper, approveReopen } = mountPanel({
      pendingReopenRequest: pendingRequest(),
      approveReopen: vi.fn().mockResolvedValue(null),
    });
    await wrapper.get("[data-testid='approve-reopen']").trigger("click");
    await wrapper.get("form").trigger("submit");

    expect(approveReopen).toHaveBeenCalled();
    expect(wrapper.find(".modal-stub").exists()).toBe(true);
    expect(wrapper.emitted("decided")).toBeUndefined();
  });

  it("Rejeitar: chama rejectReopen com o id da solicitação, fecha o modal e emite 'decided'", async () => {
    const { wrapper, rejectReopen } = mountPanel({ pendingReopenRequest: pendingRequest() });
    await wrapper.get("[data-testid='reject-reopen']").trigger("click");
    expect(wrapper.get(".modal-stub p").text()).toBe("Rejeitar reabertura");

    await wrapper.get("textarea").setValue("Não faz sentido agora.");
    await wrapper.get("form").trigger("submit");

    expect(rejectReopen).toHaveBeenCalledWith("reopen-1", "Não faz sentido agora.");
    expect(wrapper.find(".modal-stub").exists()).toBe(false);
    expect(wrapper.emitted("decided")).toHaveLength(1);
  });

  it("Decisão: cancelar no modal fecha sem chamar approveReopen/rejectReopen", async () => {
    const { wrapper, approveReopen, rejectReopen } = mountPanel({ pendingReopenRequest: pendingRequest() });
    await wrapper.get("[data-testid='approve-reopen']").trigger("click");
    await wrapper.get(".modal-stub form button[type='button']").trigger("click");

    expect(approveReopen).not.toHaveBeenCalled();
    expect(rejectReopen).not.toHaveBeenCalled();
    expect(wrapper.find(".modal-stub").exists()).toBe(false);
  });
});
