import type {
  ConditionalFormattingRule,
  Worksheet,
} from "exceljs";

export const EQUIPMENT_EXCEL_COLUMNS = [
  { header: "Equipamento", key: "equipment", width: 47.71875 },
  { header: "Unidade", key: "unit", width: 20.58984375 },
  { header: "Obra", key: "project", width: 20.58984375 },
  { header: "Área", key: "area", width: 58.6953125 },
  { header: "Disciplina", key: "discipline", width: 25.6484375 },
  { header: "Work Packages", key: "workPackages", width: 20.58984375 },
  { header: "Responsável", key: "responsible", width: 20.58984375 },
  { header: "Etapa", key: "stage", width: 47.71875 },
  { header: "Startup", key: "startup", width: 15.66015625 },
  { header: "Criticidade", key: "criticality", width: 18.6171875 },
  { header: "Componentes", key: "components", width: 13.19140625 },
] as const;

export const EQUIPMENT_EXCEL_CONDITIONAL_RULES = [
  { column: "J", text: "Longo > 180", color: "FF6645A9", priority: 1 },
  { column: "J", text: "Curto < 90", color: "FF79AFFD", priority: 2 },
  { column: "J", text: "Médio 90~180", color: "FF777AE5", priority: 3, exact: true },
  { column: "E", text: "Suprimentos", color: "FF00A8CC", priority: 4 },
  { column: "E", text: "Qualidade", color: "FF17B897", priority: 5 },
  { column: "E", text: "Projeto", color: "FF845EC2", priority: 6 },
  { column: "E", text: "Operação", color: "FF00B894", priority: 7 },
  { column: "E", text: "Automação", color: "FFE8697D", priority: 8 },
  { column: "E", text: "Civil", color: "FF216EDF", priority: 9 },
  { column: "E", text: "Elétrica e Instrumentação", color: "FFB0DC51", priority: 10 },
  { column: "E", text: "Laboratório", color: "FF0984E3", priority: 11 },
  { column: "E", text: "Manutenção", color: "FFE17055", priority: 12 },
  { column: "E", text: "Metal Mecânica.", color: "FFFF8358", priority: 13 },
  { column: "E", text: "Outros", color: "FF747D8C", priority: 14 },
  { column: "E", text: "Posto de Combustível", color: "FFB57DE3", priority: 15 },
] as const;

const centeredColumns = new Set(["B", "C", "E", "G", "I", "J", "K"]);

function ruleStyle(color: string): ConditionalFormattingRule["style"] {
  return {
    fill: {
      type: "pattern",
      pattern: "solid",
      bgColor: { argb: color },
    },
  };
}

/** Reproduz as 15 regras nativas presentes no arquivo corporativo. O alcance
 * vai até a última linha do Excel, portanto não depende do tamanho exportado. */
export function applyEquipmentConditionalFormatting(worksheet: Worksheet): void {
  const disciplineRules: ConditionalFormattingRule[] = [];
  const criticalityRules: ConditionalFormattingRule[] = [];

  for (const definition of EQUIPMENT_EXCEL_CONDITIONAL_RULES) {
    const rule: ConditionalFormattingRule = "exact" in definition && definition.exact
      ? {
          type: "expression",
          priority: definition.priority,
          formulae: [`$${definition.column}1="${definition.text}"`],
          style: ruleStyle(definition.color),
        }
      : {
          type: "containsText",
          operator: "containsText",
          priority: definition.priority,
          text: definition.text,
          style: ruleStyle(definition.color),
        };
    if (definition.column === "E") disciplineRules.push(rule);
    else criticalityRules.push(rule);
  }

  worksheet.addConditionalFormatting({
    ref: "E1:E1048576",
    rules: disciplineRules,
  });
  worksheet.addConditionalFormatting({
    ref: "J1:J1048576",
    rules: criticalityRules,
  });
}

export function applyEquipmentWorksheetStyles(worksheet: Worksheet): void {
  worksheet.columns = EQUIPMENT_EXCEL_COLUMNS.map((column) => ({ ...column }));
  worksheet.properties.defaultRowHeight = 15;
  worksheet.views = [{ state: "normal", zoomScale: 85, showGridLines: true }];
  worksheet.pageSetup.margins = {
    left: 0.511811024,
    right: 0.511811024,
    top: 0.787401575,
    bottom: 0.787401575,
    header: 0.31496062,
    footer: 0.31496062,
  };

  const header = worksheet.getRow(1);
  header.height = 30.75;
  header.font = { name: "Calibri", size: 12, bold: true, color: { argb: "FF000000" } };
  header.fill = {
    type: "pattern",
    pattern: "solid",
    fgColor: { argb: "FFD9D9D9" },
  };
  header.alignment = { horizontal: "center", vertical: "middle" };

  worksheet.getColumn("I").numFmt = "dd/mm/yyyy";
  worksheet.getColumn("K").numFmt = "0";
  applyEquipmentConditionalFormatting(worksheet);
}

export function applyEquipmentDataRowStyles(worksheet: Worksheet): void {
  worksheet.eachRow((row, rowNumber) => {
    if (rowNumber === 1) return;
    row.height = 15;
    row.font = { name: "Calibri", size: 12, color: { argb: "FF000000" } };
    row.eachCell({ includeEmpty: true }, (cell) => {
      if (centeredColumns.has(cell.col)) {
        cell.alignment = { horizontal: "center", vertical: "middle" };
      }
    });
  });
}
