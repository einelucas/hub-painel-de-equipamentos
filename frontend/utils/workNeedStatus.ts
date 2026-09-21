import type { WorkNeedStatus } from "~/types/equipment";

/**
 * Só apresentação — rótulo e cor por valor de enum já calculado pela API
 * (Etapa 6C.1). Nenhum threshold de dias é recalculado aqui; o frontend só
 * traduz o enum estável em texto/cor amigáveis. Reutiliza as classes
 * `negotiation-badge--*` (mesma linguagem visual do badge de negociação).
 */
const LABELS: Record<WorkNeedStatus, string> = {
  CHECK_DELIVERY_FUP: "Checar entrega/FUP",
  NEEDED_TODAY: "Necessita hoje",
  LT_30_DAYS: "< 30 dias",
  LT_60_DAYS: "< 60 dias",
  LT_90_DAYS: "< 90 dias",
  SAFE: "Prazo seguro",
};

const TONES: Record<WorkNeedStatus, string> = {
  CHECK_DELIVERY_FUP: "negotiation-badge--danger",
  NEEDED_TODAY: "negotiation-badge--danger",
  LT_30_DAYS: "negotiation-badge--danger",
  LT_60_DAYS: "negotiation-badge--warning",
  LT_90_DAYS: "negotiation-badge--warning",
  SAFE: "negotiation-badge--ok",
};

export function workNeedStatusLabel(status: WorkNeedStatus | null): string {
  return status ? LABELS[status] : "—";
}

export function workNeedStatusTone(status: WorkNeedStatus | null): string {
  return status ? TONES[status] : "negotiation-badge--neutral";
}
