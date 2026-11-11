import { describe, expect, it } from "vitest";
import { Workbook } from "exceljs";
import type { Equipment } from "~/types/equipment";
import { buildEquipmentWorkbook } from "~/utils/equipmentExcelExport";
import {
  EQUIPMENT_EXCEL_COLUMNS,
  EQUIPMENT_EXCEL_CONDITIONAL_RULES,
} from "~/utils/equipmentExcelStyles";

function equipment(index = 1): Equipment {
  return {
    id: `eq-${index}`,
    name: index === 1 ? "=HYPERLINK(\"https://invalid\")" : `Equipamento ${index}`,
    origin: null,
    startupAt: "2027-10-27",
    criticality: null,
    criticalityLabel: { id: "crit-1", name: "Médio 90~180" },
    currentStage: 2,
    stageName: "Equalização",
    capexEstimated: null,
    projectContext: { id: "ctx-1", code: "LEM C2", name: "Fase 2" },
    unit: { id: "unit-1", name: "Lucas do Rio Verde" },
    discipline: { id: "disc-1", name: "Civil" },
    eapNode: { id: "eap-1", code: "04.A", name: "Casa de Força", level: "AREA", active: true },
    area: null,
    supplier: null,
    operationalStatus: "ACTIVE",
    projectTotalValue: null,
    contractualDeliveryStart: null,
    contractualDeliveryEnd: null,
    workPackage: null,
    workPackages: [{ id: "wp-1", code: "CIV004", name: "CIV004" }],
    responsibleUser: { id: "user-1", name: "Responsável", email: "r@example.com" },
    componentsCount: 3,
    calculated: {
      maxLeadTimeDays: null,
      maxPreStartDays: null,
      maxFreightDays: null,
      deliveryDeadline: null,
      contractOrderDeadline: null,
      negotiationDeadline: null,
      negotiationDaysRemaining: null,
      negotiationStatus: "ON_TRACK",
      workNeedDaysRemaining: null,
      workNeedStatus: null,
    },
    createdAt: "2026-01-01",
    updatedAt: "2026-01-01",
  };
}

type ConditionalFormattingModel = {
  ref: string;
  rules: Array<{
    type: string;
    priority: number;
    text?: string;
    formulae?: string[];
    style?: { fill?: { bgColor?: { argb?: string } } };
  }>;
};

function conditionalFormatting(workbook: Workbook): ConditionalFormattingModel[] {
  const worksheet = workbook.getWorksheet("Dados");
  return ((worksheet?.model as unknown as { conditionalFormattings?: ConditionalFormattingModel[] })
    .conditionalFormattings ?? []);
}

describe("exportação de equipamentos com ExcelJS", () => {
  it("reproduz as 11 colunas, dimensões e tipos do modelo corporativo", async () => {
    const workbook = await buildEquipmentWorkbook([equipment()]);
    const worksheet = workbook.getWorksheet("Dados")!;

    expect(worksheet.columns.map((column) => column.header)).toEqual(
      EQUIPMENT_EXCEL_COLUMNS.map((column) => column.header),
    );
    expect(worksheet.columns.map((column) => column.width)).toEqual(
      EQUIPMENT_EXCEL_COLUMNS.map((column) => column.width),
    );
    expect(worksheet.getRow(1).height).toBe(30.75);
    expect(worksheet.getRow(1).font).toMatchObject({ name: "Calibri", size: 12, bold: true });
    expect(worksheet.getRow(2).height).toBe(15);
    expect(worksheet.getCell("C2").value).toBe("LEM C2");
    expect(worksheet.getCell("I2").value).toBeInstanceOf(Date);
    expect(worksheet.getCell("I2").numFmt).toBe("dd/mm/yyyy");
    expect(worksheet.getCell("K2").value).toBe(3);
    expect(worksheet.getCell("K2").numFmt).toBe("0");
    expect(worksheet.getCell("A2").value).toBe('=HYPERLINK("https://invalid")');
    expect(worksheet.getCell("A2").type).toBe(3);
  });

  it("serializa as 15 regras condicionais nativas até a última linha do Excel", async () => {
    const workbook = await buildEquipmentWorkbook([equipment()]);
    const buffer = await workbook.xlsx.writeBuffer();
    const reloaded = new Workbook();
    await reloaded.xlsx.load(buffer);
    const groups = conditionalFormatting(reloaded);
    const rules = groups.flatMap((group) => group.rules);

    expect(groups.map((group) => group.ref)).toEqual(["E1:E1048576", "J1:J1048576"]);
    expect(rules).toHaveLength(15);
    expect(rules.map((rule) => rule.priority).sort((a, b) => a - b)).toEqual(
      EQUIPMENT_EXCEL_CONDITIONAL_RULES.map((rule) => rule.priority),
    );
    expect(rules.filter((rule) => rule.type === "containsText")).toHaveLength(14);
    expect(rules.filter((rule) => rule.type === "expression")).toHaveLength(1);
    expect(
      [...rules]
        .sort((a, b) => a.priority - b.priority)
        .map((rule) => rule.style?.fill?.bgColor?.argb),
    ).toEqual(EQUIPMENT_EXCEL_CONDITIONAL_RULES.map((rule) => rule.color));
  });

  it.each([1, 100, 500])("exporta %i registros sem truncar linhas", async (count) => {
    const workbook = await buildEquipmentWorkbook(
      Array.from({ length: count }, (_, index) => equipment(index + 1)),
    );
    expect(workbook.getWorksheet("Dados")?.rowCount).toBe(count + 1);
  });
});
