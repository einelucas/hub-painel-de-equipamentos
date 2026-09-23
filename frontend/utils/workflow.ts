import type { OperationalStatus, TransitionOption, WorkflowExceptionType } from "~/types/equipment";
import { EQUIPMENT_STAGES } from "~/utils/stages";

/** Etapa 7A: só negociação e jurídico continuam com forma 1:1 editável
 * "na etapa atual" — Contrato/SC-OCI/OC viraram listas 1:N (seção
 * "Processo completo", componentes dedicados de lista). */
export type ProcessResource = "negotiation" | "legal";

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
  5: null,
  6: null,
  7: null,
  8: null,
};

/** Formulário que o usuário opera na etapa informada. `null` = etapa sem edição
 * inline (fases 5/6/7 usam as listas de Contratos/SC-OCI/OC abaixo). */
export function resourceForStage(stage: number): ProcessResource | null {
  return RESOURCE_BY_STAGE[stage] ?? null;
}

export const OPERATIONAL_STATUS_LABELS: Record<OperationalStatus, string> = {
  ACTIVE: "Ativo",
  STANDBY: "Standby",
  CANCELLED: "Cancelado",
  IN_SANITATION: "Em Saneamento",
};

export const WORKFLOW_EXCEPTION_LABELS: Record<WorkflowExceptionType, string> = {
  FIXED_SUPPLIER: "Fornecedor fixo",
  IMPORTATION: "Importação",
};

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
