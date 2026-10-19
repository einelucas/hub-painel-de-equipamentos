import type {
  OperationalStatus,
  OperationalStatusEvent,
  RequirementWaiverReasonCode,
  TransitionOption,
  WorkflowTransition,
} from "~/types/equipment";
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

/** Etapa 7.1: motivo da dispensa — só classificação/auditoria, nunca
 * determina quais grupos são dispensáveis (isso é decidido pelo backend). */
export const REQUIREMENT_WAIVER_REASON_LABELS: Record<RequirementWaiverReasonCode, string> = {
  IMPORTATION: "Importação",
  FIXED_SUPPLIER: "Fornecedor fixo",
  EXCEPTIONAL_PROCESS: "Processo excepcional",
  OTHER: "Outro",
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

/**
 * Data em que o equipamento entrou na etapa atual.
 *
 * O marco vem da transição mais recente PARA a etapa (histórico do workflow).
 * A etapa 0 é a exceção: também se chega nela sem transição — cadastro novo ou
 * retorno de Saneamento (que devolve o equipamento para "Nova demanda" sem
 * gravar transição), por isso lá vale a data mais recente entre cadastro e
 * entrada em Saneamento.
 *
 * `null` quando não existe marco confiável: equipamento importado do Monday,
 * que grava `current_stage` direto, sem passar pelo serviço de transição. Nesse
 * caso a tela não mostra data nenhuma em vez de inventar uma.
 */
export function currentStageEnteredAt(input: {
  currentStage: number;
  createdAt: string | null;
  history: WorkflowTransition[];
  operationalEvents?: OperationalStatusEvent[];
}): string | null {
  const transitions = input.history.filter((entry) => entry.toStage === input.currentStage);

  if (transitions.length > 0) {
    return transitions.reduce(
      (latest, entry) => (entry.occurredAt > latest ? entry.occurredAt : latest),
      transitions[0]!.occurredAt,
    );
  }

  if (input.currentStage !== 0) return null;

  const sanitationEntries = (input.operationalEvents ?? [])
    .filter((event) => event.kind === "SANITATION_ENTERED")
    .map((event) => event.occurredAt)
    .sort();

  const candidates = [sanitationEntries.at(-1) ?? null, input.createdAt].filter(
    (value): value is string => Boolean(value),
  );

  if (candidates.length === 0) return null;
  return candidates.reduce((latest, value) => (value > latest ? value : latest));
}

export function blankToNull(value: string): string | null {
  return value.trim() === "" ? null : value.trim();
}
