import type { DashboardSummary, StageDistribution } from "~/types/equipment";

export interface ChartPoint {
  label: string;
  value: number;
}

export interface DonutItem {
  label: string;
  value: number;
  color: string;
}

export const FINAL_STAGE = 8;

/** Barras da distribuição por etapa, na ordem do catálogo 0–8. */
export function stageChartPoints(workflow: StageDistribution[]): ChartPoint[] {
  return workflow.map((item) => ({ label: `${item.stage}. ${item.name}`, value: item.count }));
}

/**
 * Situação geral: agrupa as contagens já agregadas pelo backend em três
 * categorias do próprio catálogo. Nenhum estado novo é inventado.
 */
export function situationDonut(workflow: StageDistribution[]): DonutItem[] {
  const at = (stage: number) => workflow.find((item) => item.stage === stage)?.count ?? 0;
  const total = workflow.reduce((sum, item) => sum + item.count, 0);
  const newDemand = at(0);
  const completed = at(FINAL_STAGE);
  return [
    { label: "Nova demanda", value: newDemand, color: "#8697ad" },
    { label: "Em processo", value: total - newDemand - completed, color: "#304f7e" },
    { label: "Concluído", value: completed, color: "#609346" },
  ];
}

/** Percentual de negociações registradas; null quando não há base para calcular. */
export function negotiationProgress(summary: DashboardSummary): number | null {
  const { open, completed } = summary.negotiation;
  const total = open + completed;
  if (total === 0) return null;
  return (completed / total) * 100;
}

export interface NegotiationProgressItem {
  label: string;
  value: number;
}

/**
 * As 3 barras do card de Negociação (Concluídas/Em aberto/Em negociação),
 * todas sobre o mesmo denominador já usado por `negotiationProgress`
 * (`open + completed` — nenhuma regra nova). Lista vazia quando não há base
 * para calcular, mesmo critério de "sem dados" da barra única anterior.
 */
export function negotiationProgressBars(negotiation: DashboardSummary["negotiation"]): NegotiationProgressItem[] {
  const { open, completed, inNegotiation } = negotiation;
  const total = open + completed;
  if (total === 0) return [];
  return [
    { label: "Negociações concluídas", value: (completed / total) * 100 },
    { label: "Em aberto", value: (open / total) * 100 },
    { label: "Em negociação/equalização", value: (inNegotiation / total) * 100 },
  ];
}

/**
 * Widget do Monday "Status dos prazos de negociação": traduz a agregação já
 * pronta do backend (`NegotiationDeadlineStatusSummary`, GAP-014) em fatias
 * de donut — nenhum threshold é recalculado aqui, só rótulo/cor por
 * categoria já contada pela API. Ordem do mais urgente ao mais seguro,
 * mesmo critério de prioridade visual do card "Situação de prazos". Cores
 * reaproveitadas do design system existente (vermelho/laranja de risco já
 * usados nos badges de status, azul institucional de "Em processo", verde
 * de "Concluído" — nenhuma cor nova).
 */
export function negotiationDeadlineStatusDonut(
  summary: DashboardSummary["negotiationDeadlineStatus"],
): DonutItem[] {
  return [
    { label: "Atrasado", value: summary.overdue, color: "#a53f3f" },
    { label: "Urgente", value: summary.urgent, color: "#cc5121" },
    { label: "Próximo", value: summary.upcoming, color: "#d3a24d" },
    { label: "No prazo", value: summary.onTrack, color: "#304f7e" },
    { label: "Concluído", value: summary.completed, color: "#609346" },
  ];
}

export function startupLabel(summary: DashboardSummary): string {
  const { daysRemaining } = summary.startup;
  if (daysRemaining === null) return "Sem startup futura no recorte";
  if (daysRemaining === 0) return "Startup hoje";
  return `Em ${daysRemaining} dia${daysRemaining === 1 ? "" : "s"}`;
}
