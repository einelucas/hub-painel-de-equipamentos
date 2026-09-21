import type { NegotiationStatus } from "~/types/equipment";

/**
 * Só apresentação — rótulo e cor por valor de enum já calculado pela API
 * (GAP-014). Nenhum threshold de dias é recalculado aqui; o frontend só
 * traduz o enum estável em texto/cor amigáveis.
 */
const LABELS: Record<NegotiationStatus, string> = {
  NOT_APPLICABLE: "Não se aplica",
  COMPLETED: "Concluído",
  OVERDUE: "Atrasado",
  DUE_TODAY: "Vence hoje",
  CRITICAL: "Crítico",
  URGENT: "Urgente",
  UPCOMING: "Próximo",
  ON_TRACK: "No prazo",
};

const TONES: Record<NegotiationStatus, string> = {
  NOT_APPLICABLE: "negotiation-badge--neutral",
  COMPLETED: "negotiation-badge--complete",
  OVERDUE: "negotiation-badge--danger",
  DUE_TODAY: "negotiation-badge--danger",
  CRITICAL: "negotiation-badge--danger",
  URGENT: "negotiation-badge--warning",
  UPCOMING: "negotiation-badge--warning",
  ON_TRACK: "negotiation-badge--ok",
};

export function negotiationStatusLabel(status: NegotiationStatus | null): string {
  return status ? LABELS[status] : "—";
}

export function negotiationStatusTone(status: NegotiationStatus | null): string {
  return status ? TONES[status] : "negotiation-badge--neutral";
}
