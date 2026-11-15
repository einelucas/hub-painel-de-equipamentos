/** Exportação dos resultados calculados, separada dos dados operacionais. */
import type { StartupScenario } from "~/types/startupSimulation";
import { formatScenarioDate } from "~/utils/startupSimulation";

export async function exportStartupScenarios(scenarios: StartupScenario[]): Promise<void> {
  if (!scenarios.length) return;
  const { Workbook } = await import("exceljs");
  const workbook = new Workbook();
  workbook.creator = "INPASA · Hub de Automação";
  const overview = workbook.addWorksheet("VISÃO EXECUTIVA");
  overview.addRow(["SIMULAÇÕES DE STARTUP", ...scenarios.map((s) => s.name)]);
  const metrics: Array<[string, (s: StartupScenario) => string | number]> = [
    ["Equipamentos", (s) => s.summary.equipments],
    ["Startup", (s) => formatScenarioDate(s.startupAt)],
    ["Primeira negociação", (s) => formatScenarioDate(s.summary.firstNegotiation)],
    ["Última negociação", (s) => formatScenarioDate(s.summary.lastNegotiation)],
    ["Primeira entrega", (s) => formatScenarioDate(s.summary.firstDelivery)],
    ["Última entrega", (s) => formatScenarioDate(s.summary.lastDelivery)],
    ["Fabricação média (dias)", (s) => s.summary.averageManufactureDays ?? "—"],
    ["Antecedência média (dias)", (s) => s.summary.averagePreStartDays ?? "—"],
  ];
  metrics.forEach(([label, getter]) => overview.addRow([label, ...scenarios.map(getter)]));
  overview.getColumn(1).width = 32;
  scenarios.forEach((_s, index) => { overview.getColumn(index + 2).width = 26; });
  overview.getRow(1).font = { bold: true, color: { argb: "FFFFFFFF" } };
  overview.getRow(1).fill = { type: "pattern", pattern: "solid", fgColor: { argb: "FF304F7E" } };

  for (const [index, scenario] of scenarios.entries()) {
    const sheet = workbook.addWorksheet(`CENARIO ${index + 1}`);
    sheet.addRow(["Equipamento", "Origem", "Disciplina", "Fornecedor", "Área", "Responsável",
      "Limite negociação", "Limite contrato OC", "Limite entrega", "Startup próprio/geral",
      "Suprimentos (dias)", "Jurídico (dias)", "Fabricação (dias)", "Dias antes startup"]);
    for (const row of scenario.items) {
      sheet.addRow([
        row.name, row.origin, row.discipline, row.supplier, row.area, row.responsible,
        formatScenarioDate(row.negotiationDeadline), formatScenarioDate(row.contractDeadline),
        formatScenarioDate(row.deliveryDeadline), formatScenarioDate(row.startupAt || scenario.startupAt),
        row.suppliesDays, row.legalDays, row.manufactureDays, row.preStartDays,
      ]);
    }
    const header = sheet.getRow(1);
    header.font = { bold: true, color: { argb: "FFFFFFFF" } };
    header.fill = { type: "pattern", pattern: "solid", fgColor: { argb: "FF304F7E" } };
    sheet.views = [{ state: "frozen", ySplit: 1 }];
    sheet.autoFilter = { from: { row: 1, column: 1 }, to: { row: scenario.items.length + 1, column: 14 } };
    sheet.columns.forEach((column, idx) => { column.width = idx === 0 ? 42 : idx < 6 ? 20 : 17; });
  }

  const buffer = await workbook.xlsx.writeBuffer();
  const blob = new Blob([buffer as BlobPart], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "Simulacoes_Startup_Hub.xlsx";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
