import type { Equipment } from "~/types/equipment";

/** Recorte executivo por EQUIPAMENTO. Componentes são informados separadamente:
 * não existe equivalência aprovada entre subitem e aquisição financeira. */
export interface EquipmentReportMetrics {
  total: number;
  components: number;
  completed: number;
  onTime: number;
  overdue: number;
  unclassified: number;
  earlyStage: number;
  completedPercent: number;
  onTimePercent: number;
  overduePercent: number;
  unclassifiedPercent: number;
  nextStartup: string | null;
  daysToNextStartup: number | null;
  overdueEquipments: Array<{ equipment: Equipment; daysLate: number | null }>;
  pipeline: Array<{ stage: number; label: string; count: number }>;
}

const ON_TIME = new Set(["DUE_TODAY", "CRITICAL", "URGENT", "UPCOMING", "ON_TRACK"]);
const NEGOTIATION_STAGES = new Set([0, 1, 2]);
const PIPELINE = [
  { stage: 3, label: "Abertura de Chamado" },
  { stage: 4, label: "Aprovação de Minuta" },
  { stage: 5, label: "Escrituração de Contrato" },
  { stage: 6, label: "SC/OCI" },
  { stage: 7, label: "Aprovação de Ordem de Compra" },
  { stage: 8, label: "Concluído" },
] as const;

function calendarDay(date: string | null | undefined): number | null {
  const match = date?.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!match) return null;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const dateUtc = Date.UTC(year, month - 1, day);
  const check = new Date(dateUtc);
  if (check.getUTCFullYear() !== year || check.getUTCMonth() + 1 !== month || check.getUTCDate() !== day) {
    return null;
  }
  return Math.floor(dateUtc / 86_400_000);
}

export function formatReportDate(value: string | null | undefined): string {
  const day = calendarDay(value);
  if (day === null) return "Não informada";
  const date = new Date(day * 86_400_000);
  const d = String(date.getUTCDate()).padStart(2, "0");
  const m = String(date.getUTCMonth() + 1).padStart(2, "0");
  return `${d}/${m}/${date.getUTCFullYear()}`;
}

export function reportPercent(part: number, total: number): number {
  return total > 0 ? (part / total) * 100 : 0;
}

/** Usa somente os cálculos oficiais que a API já entrega. Não interpreta fase
 * como prova de negociação concluída e não inventa uma data-limite ausente. */
export function buildEquipmentReport(
  equipments: Equipment[],
  generatedAt: Date = new Date(),
): EquipmentReportMetrics {
  const total = equipments.length;
  const today = Math.floor(Date.UTC(
    generatedAt.getFullYear(), generatedAt.getMonth(), generatedAt.getDate(),
  ) / 86_400_000);
  let completed = 0;
  let onTime = 0;
  let unclassified = 0;
  let components = 0;
  const overdueEquipments: EquipmentReportMetrics["overdueEquipments"] = [];
  const pipeline = PIPELINE.map(({ stage, label }) => ({ stage, label, count: 0 }));
  let nextStartup: string | null = null;
  let nextStartupDay: number | null = null;

  for (const equipment of equipments) {
    components += Math.max(0, equipment.componentsCount || 0);
    const pipelineStage = pipeline.find((item) => item.stage === equipment.currentStage);
    if (pipelineStage) pipelineStage.count++;

    const status = equipment.calculated?.negotiationStatus;
    if (status === "COMPLETED") completed++;
    else if (status === "OVERDUE" && NEGOTIATION_STAGES.has(equipment.currentStage)) {
      const apiDays = equipment.calculated?.negotiationDaysRemaining;
      const deadlineDay = calendarDay(equipment.calculated?.negotiationDeadline);
      const daysLate = typeof apiDays === "number" && Number.isFinite(apiDays) && apiDays < 0
        ? Math.abs(apiDays)
        : deadlineDay !== null && deadlineDay < today ? today - deadlineDay : null;
      overdueEquipments.push({ equipment, daysLate });
    } else if (status && ON_TIME.has(status)) onTime++;
    else unclassified++;

    const startupDay = calendarDay(equipment.startupAt);
    if (startupDay !== null && startupDay >= today && (nextStartupDay === null || startupDay < nextStartupDay)) {
      nextStartupDay = startupDay;
      nextStartup = equipment.startupAt;
    }
  }

  overdueEquipments.sort((a, b) =>
    (b.daysLate ?? -1) - (a.daysLate ?? -1) ||
    a.equipment.name.localeCompare(b.equipment.name, "pt-BR"),
  );
  const overdue = overdueEquipments.length;
  return {
    total,
    components,
    completed,
    onTime,
    overdue,
    unclassified,
    earlyStage: equipments.filter((item) => item.currentStage <= 2).length,
    completedPercent: reportPercent(completed, total),
    onTimePercent: reportPercent(onTime, total),
    overduePercent: reportPercent(overdue, total),
    unclassifiedPercent: reportPercent(unclassified, total),
    nextStartup,
    daysToNextStartup: nextStartupDay === null ? null : nextStartupDay - today,
    overdueEquipments,
    pipeline,
  };
}

export function chunks<T>(items: T[], size: number): T[][] {
  if (!Number.isInteger(size) || size < 1) throw new Error("Tamanho de página inválido");
  if (!items.length) return [[]];
  const result: T[][] = [];
  for (let i = 0; i < items.length; i += size) result.push(items.slice(i, i + size));
  return result;
}
