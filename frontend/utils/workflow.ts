import type { TransitionOption } from "~/types/equipment";
import { EQUIPMENT_STAGES } from "~/utils/stages";

export type ProcessResource =
  | "negotiation"
  | "legal"
  | "contract"
  | "purchase-request"
  | "purchase-order";

export type StepState = "done" | "current" | "blocked" | "future";

export interface WorkflowStep {
  index: number;
  label: string;
  state: StepState;
}

const RESOURCE_BY_STAGE: Record<number, ProcessResource | null> = {
  0: null,
  1: "negotiation",
  2: "negotiation",
  3: "legal",
  4: "legal",
  5: "contract",
  6: "purchase-request",
  7: "purchase-order",
  8: null,
};

/** Formulário que o usuário opera na etapa informada. `null` = etapa sem edição. */
export function resourceForStage(stage: number): ProcessResource | null {
  return RESOURCE_BY_STAGE[stage] ?? null;
}

export function stepStates(currentStage: number, nextStageBlocked = false): WorkflowStep[] {
  return EQUIPMENT_STAGES.map((label, index) => {
    let state: StepState = "future";
    if (index < currentStage) state = "done";
    else if (index === currentStage) state = "current";
    else if (index === currentStage + 1 && nextStageBlocked) state = "blocked";
    return { index, label, state };
  });
}

export function advanceLabel(option: TransitionOption | null): string {
  if (!option) return "";
  return option.targetStage === 1 ? "Iniciar negociação" : `Avançar para ${option.targetStageLabel}`;
}

export function blankToNull(value: string): string | null {
  return value.trim() === "" ? null : value.trim();
}
