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

export function startupLabel(summary: DashboardSummary): string {
  const { daysRemaining } = summary.startup;
  if (daysRemaining === null) return "Sem startup futura no recorte";
  if (daysRemaining === 0) return "Startup hoje";
  return `Em ${daysRemaining} dia${daysRemaining === 1 ? "" : "s"}`;
}
