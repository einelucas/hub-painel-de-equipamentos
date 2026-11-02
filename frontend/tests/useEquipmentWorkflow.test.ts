import { computed, ref } from "vue";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useEquipmentWorkflow } from "~/composables/useEquipmentWorkflow";
import type { ReopenRequest } from "~/types/equipment";

const api = {
  get: vi.fn(),
  post: vi.fn(),
  patch: vi.fn(),
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.stubGlobal("ref", ref);
  vi.stubGlobal("computed", computed);
  vi.stubGlobal("useApi", () => api);
});

describe("useEquipmentWorkflow — reabertura", () => {
  it("usa a resposta da solicitação sem recarregar toda a aba Processo", async () => {
    const created: ReopenRequest = {
      id: "reopen-1",
      equipmentId: "eq-1",
      sourceStage: 5,
      sourceStageLabel: "Escrituração do contrato",
      targetStage: 2,
      targetStageLabel: "Equalização",
      justification: "Revisar equalização",
      status: "PENDING",
      requestedBy: null,
      requestedAt: "2026-11-02T12:00:00Z",
      decidedBy: null,
      decidedAt: null,
      decisionNote: null,
    };
    api.post.mockResolvedValue(created);

    const workflow = useEquipmentWorkflow(ref("eq-1"));
    const result = await workflow.requestReopen(2, "Revisar equalização");

    expect(result).toEqual(created);
    expect(api.post).toHaveBeenCalledWith("/equipments/eq-1/reopen-requests", {
      targetStage: 2,
      justification: "Revisar equalização",
    });
    expect(api.get).not.toHaveBeenCalled();
    expect(workflow.pendingReopenRequest.value).toEqual(created);
    expect(workflow.actionSuccess.value).toBe(
      "Solicitação de reabertura enviada para aprovação.",
    );
    expect(workflow.error.value).toBe("");
  });

  it("mantém o erro da solicitação no painel sem invalidar o processo", async () => {
    api.post.mockRejectedValue(new Error("Falha ao solicitar reabertura"));
    const workflow = useEquipmentWorkflow(ref("eq-1"));

    const result = await workflow.requestReopen(1, "Revisar negociação");

    expect(result).toBeNull();
    expect(api.get).not.toHaveBeenCalled();
    expect(workflow.actionError.value).toBe("Falha ao solicitar reabertura");
    expect(workflow.error.value).toBe("");
  });
});
