import { describe, expect, it } from "vitest";
import type { TransitionOption } from "~/types/equipment";
import { advanceLabel, blankToNull, resourceForStage, stepStates } from "~/utils/workflow";

function option(overrides: Partial<TransitionOption> = {}): TransitionOption {
  return {
    targetStage: 6,
    targetStageLabel: "SC ou OCI",
    kind: "advance",
    canExecute: false,
    requiresReason: false,
    blockedReason: null,
    requirements: [],
    satisfiedRequirements: [],
    missingRequirements: [],
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
  it("mapeia cada etapa ao formulário que o usuário opera", () => {
    expect(resourceForStage(0)).toBeNull();
    expect(resourceForStage(1)).toBe("negotiation");
    expect(resourceForStage(2)).toBe("negotiation");
    expect(resourceForStage(3)).toBe("legal");
    expect(resourceForStage(4)).toBe("legal");
    expect(resourceForStage(5)).toBe("contract");
    expect(resourceForStage(6)).toBe("purchase-request");
    expect(resourceForStage(7)).toBe("purchase-order");
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
