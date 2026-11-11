import type { Workbook } from "exceljs";
import type { Equipment } from "~/types/equipment";
import { equipmentLocationLabel } from "~/utils/equipmentLocation";
import {
  applyEquipmentDataRowStyles,
  applyEquipmentWorksheetStyles,
} from "~/utils/equipmentExcelStyles";

function safeText(value: unknown): string {
  return value == null ? "" : String(value);
}

function excelDate(value: string | null): Date | null {
  const match = value?.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!match) return null;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const date = new Date(Date.UTC(year, month - 1, day));
  return date.getUTCFullYear() === year
    && date.getUTCMonth() + 1 === month
    && date.getUTCDate() === day
    ? date
    : null;
}

export function equipmentExcelRow(equipment: Equipment): Record<string, string | number | Date | null> {
  return {
    equipment: safeText(equipment.name),
    unit: safeText(equipment.unit.name),
    project: safeText(equipment.projectContext.code ?? equipment.projectContext.name),
    area: safeText(equipmentLocationLabel(equipment)),
    discipline: safeText(equipment.discipline?.name),
    workPackages: equipment.workPackages.map((item) => item.code ?? item.name).join(", "),
    responsible: safeText(equipment.responsibleUser?.name),
    stage: `${equipment.currentStage} · ${safeText(equipment.stageName)}`,
    startup: excelDate(equipment.startupAt),
    criticality: safeText(equipment.criticalityLabel?.name ?? equipment.criticality),
    components: Math.max(0, equipment.componentsCount || 0),
  };
}

export async function buildEquipmentWorkbook(equipments: Equipment[]): Promise<Workbook> {
  const { Workbook } = await import("exceljs");
  const workbook = new Workbook();
  workbook.creator = "INPASA · Hub de Automação";
  workbook.created = new Date();
  workbook.modified = new Date();
  workbook.calcProperties.fullCalcOnLoad = true;
  const worksheet = workbook.addWorksheet("Dados");
  applyEquipmentWorksheetStyles(worksheet);
  for (const equipment of equipments) worksheet.addRow(equipmentExcelRow(equipment));
  applyEquipmentDataRowStyles(worksheet);
  return workbook;
}

function normalizedFileName(fileName: string): string {
  return fileName.toLowerCase().endsWith(".xlsx") ? fileName : `${fileName}.xlsx`;
}

export async function downloadEquipmentWorkbook(
  fileName: string,
  equipments: Equipment[],
): Promise<void> {
  const workbook = await buildEquipmentWorkbook(equipments);
  const buffer = await workbook.xlsx.writeBuffer();
  const bytes = new Uint8Array(buffer as ArrayBuffer);
  const blob = new Blob([bytes.buffer as ArrayBuffer], {
    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = normalizedFileName(fileName);
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 10_000);
}
