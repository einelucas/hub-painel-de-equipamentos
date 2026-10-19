import { describe, expect, it } from "vitest";
import type { OperationalStatusEvent, TransitionOption, WorkflowTransition } from "~/types/equipment";
import {
  advanceLabel,
  blankToNull,
  currentStageEnteredAt,
  resourceForStage,
  stepStates,
} from "~/utils/workflow";

function transition(overrides: Partial<WorkflowTransition> = {}): WorkflowTransition {
  return {
    id: "tr-1",
    fromStage: 0,
    fromStageName: "Nova demanda",
    toStage: 1,
    toStageName: "Negociação",
    reason: null,
    actor: null,
    occurredAt: "2026-03-10T12:00:00.000Z",
    ...overrides,
  };
}

function sanitationEvent(occurredAt: string): OperationalStatusEvent {
  return {
    id: `ev-${occurredAt}`,
    kind: "SANITATION_ENTERED",
    resultingStatus: "IN_SANITATION",
    stageAtEvent: 4,
    justification: "Retorno para saneamento",
    actor: null,
    occurredAt,
  };
}

function option(overrides: Partial<TransitionOption> = {}): TransitionOption {
  return {
    targetStage: 6,
    targetStageLabel: "SC ou OCI",
    kind: "advance",
    canExecute: false,
    requiresReason: false,
    blockedReason: null,
    requirementGroups: [],
    ...overrides,
  };
}

describe("stepStates", () => {
  it("expõe as nove etapas do catálogo 0–8", () => {
    const steps = stepStates(0);
    expect(steps).toHaveLength(9);
    expect(steps.map((step) => step.index)).toEqual([0, 1, 2, 3, 4, 5, 6, 7, 8]);
    expect(steps[1]!.label).toBe("Negociação");
  });

  it("marca etapas anteriores como concluídas e destaca a atual", () => {
    const steps = stepStates(3);
    expect(steps.slice(0, 3).every((step) => step.state === "done")).toBe(true);
    expect(steps[3]!.state).toBe("current");
    expect(steps[4]!.state).toBe("future");
  });

  it("sinaliza a próxima etapa como bloqueada quando há requisito pendente", () => {
    expect(stepStates(3, true)[4]!.state).toBe("blocked");
    expect(stepStates(3, false)[4]!.state).toBe("future");
  });
});

describe("resourceForStage", () => {
  it("mapeia cada etapa ao formulário que o usuário opera — Etapa 7A: 5/6/7 viraram listas 1:N, sem formulário inline", () => {
    expect(resourceForStage(0)).toBeNull();
    expect(resourceForStage(1)).toBe("negotiation");
    expect(resourceForStage(2)).toBe("negotiation");
    expect(resourceForStage(3)).toBe("legal");
    expect(resourceForStage(4)).toBe("legal");
    expect(resourceForStage(5)).toBeNull();
    expect(resourceForStage(6)).toBeNull();
    expect(resourceForStage(7)).toBeNull();
    expect(resourceForStage(8)).toBeNull();
  });
});

describe("advanceLabel", () => {
  it("usa rótulo próprio para o início da negociação", () => {
    expect(advanceLabel(option({ targetStage: 1, targetStageLabel: "Negociação" }))).toBe(
      "Iniciar negociação",
    );
  });

  it("nomeia a etapa de destino nas demais transições", () => {
    expect(advanceLabel(option())).toBe("Avançar para SC ou OCI");
  });

  it("não rotula quando não há transição disponível", () => {
    expect(advanceLabel(null)).toBe("");
  });
});

describe("blankToNull", () => {
  it("converte campo vazio em null e preserva o conteúdo digitado", () => {
    expect(blankToNull("   ")).toBeNull();
    expect(blankToNull(" CT-01 ")).toBe("CT-01");
  });
});

describe("currentStageEnteredAt", () => {
  it("usa a transição mais recente para a etapa atual", () => {
    const entered = currentStageEnteredAt({
      currentStage: 3,
      createdAt: "2026-01-01T10:00:00.000Z",
      history: [
        transition({ id: "a", toStage: 1, occurredAt: "2026-02-01T10:00:00.000Z" }),
        transition({ id: "b", fromStage: 1, toStage: 2, occurredAt: "2026-02-10T10:00:00.000Z" }),
        transition({ id: "c", fromStage: 2, toStage: 3, occurredAt: "2026-03-05T10:00:00.000Z" }),
      ],
    });

    expect(entered).toBe("2026-03-05T10:00:00.000Z");
  });

  it("considera a última entrada quando a etapa foi reaberta (reentrada)", () => {
    const entered = currentStageEnteredAt({
      currentStage: 3,
      createdAt: "2026-01-01T10:00:00.000Z",
      history: [
        transition({ id: "ida", fromStage: 2, toStage: 3, occurredAt: "2026-03-05T10:00:00.000Z" }),
        transition({ id: "volta", fromStage: 6, toStage: 3, occurredAt: "2026-04-01T09:00:00.000Z" }),
      ],
    });

    expect(entered).toBe("2026-04-01T09:00:00.000Z");
  });

  it("na etapa 0 sem transição usa a data de cadastro", () => {
    const entered = currentStageEnteredAt({
      currentStage: 0,
      createdAt: "2026-05-20T08:00:00.000Z",
      history: [],
    });

    expect(entered).toBe("2026-05-20T08:00:00.000Z");
  });

  it("na etapa 0 usa o retorno de Saneamento quando ele é mais recente que o cadastro", () => {
    const entered = currentStageEnteredAt({
      currentStage: 0,
      createdAt: "2026-05-20T08:00:00.000Z",
      history: [transition({ id: "a", toStage: 4, occurredAt: "2026-05-25T08:00:00.000Z" })],
      operationalEvents: [
        sanitationEvent("2026-06-02T08:00:00.000Z"),
        sanitationEvent("2026-05-30T08:00:00.000Z"),
      ],
    });

    expect(entered).toBe("2026-06-02T08:00:00.000Z");
  });

  it("não inventa data para etapa sem transição registrada (importado do Monday)", () => {
    const entered = currentStageEnteredAt({
      currentStage: 5,
      createdAt: "2025-11-03T08:00:00.000Z",
      history: [transition({ id: "a", toStage: 1, occurredAt: "2025-11-04T08:00:00.000Z" })],
    });

    expect(entered).toBeNull();
  });

  it("devolve null quando não há nem transição nem cadastro", () => {
    expect(currentStageEnteredAt({ currentStage: 0, createdAt: null, history: [] })).toBeNull();
  });
});
