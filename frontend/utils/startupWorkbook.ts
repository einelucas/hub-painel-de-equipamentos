/** Importação client-side: não executa fórmulas da planilha, lê apenas colunas A-F e J-N. */
import type { StartupItemInput } from "~/types/startupSimulation";

export interface ImportedScenario {
  name: string;
  startupAt: string;
  items: StartupItemInput[];
}

export interface ImportedWorkbook {
  scenarios: ImportedScenario[];
  warnings: string[];
}

function unwrap(value: unknown): unknown {
  if (value && typeof value === "object" && "result" in value) {
    return (value as { result: unknown }).result;
  }
  if (value && typeof value === "object" && "text" in value) {
    return (value as { text: unknown }).text;
  }
  return value;
}

function asText(value: unknown): string {
  const actual = unwrap(value);
  return actual == null ? "" : String(actual).trim();
}

function asIso(value: unknown): string | null {
  const actual = unwrap(value);
  if (actual instanceof Date && !Number.isNaN(actual.getTime())) return actual.toISOString().slice(0, 10);
  if (typeof actual === "number" && actual >= 1 && actual <= 2958465) {
    return new Date(Date.UTC(1899, 11, 30) + Math.floor(actual) * 86400000).toISOString().slice(0, 10);
  }
  const text = asText(actual);
  if (/^\d{4}-\d{2}-\d{2}$/.test(text)) return text;
  if (/^\d{2}\/\d{2}\/\d{4}$/.test(text)) {
    const [d, m, y] = text.split("/");
    return `${y}-${m}-${d}`;
  }
  return null;
}

function days(value: unknown, location: string, warnings: string[]): number | null {
  const actual = unwrap(value);
  if (actual === null || actual === undefined || actual === "") return null;
  const number = typeof actual === "number" ? actual : Number(actual);
  if (!Number.isInteger(number) || number < 0 || number > 36500) {
    warnings.push(`${location}: prazo inválido (${String(actual)}), campo ignorado.`);
    return null;
  }
  return number;
}

export async function readStartupWorkbook(file: File): Promise<ImportedWorkbook> {
  if (!/\.xlsx$/i.test(file.name)) throw new Error("Selecione uma planilha .xlsx.");
  if (file.size > 8 * 1024 * 1024) throw new Error("O arquivo ultrapassa 8 MB.");
  const { Workbook } = await import("exceljs");
  const workbook = new Workbook();
  await workbook.xlsx.load(new Uint8Array(await file.arrayBuffer()) as unknown as Buffer);
  const warnings: string[] = [];
  const scenarios: ImportedScenario[] = [];
  for (const sheet of workbook.worksheets) {
    const match = sheet.name.match(/PLAN EQUIPAMENTOS.*(20\d{2})/i);
    if (!match) continue;
    const items: StartupItemInput[] = [];
    let startup: string | null = null;
    for (let rowNum = 3; rowNum <= sheet.rowCount; rowNum += 1) {
      const row = sheet.getRow(rowNum);
      const name = asText(row.getCell(3).value);
      if (!name) continue;
      if (items.length >= 500) throw new Error("Limite de 500 equipamentos por cenário.");
      const lineStartup = asIso(row.getCell(10).value);
      if (lineStartup && !startup) startup = lineStartup;
      const location = `${sheet.name}, linha ${rowNum}`;
      items.push({
        equipmentId: null,
        name,
        origin: asText(row.getCell(1).value) || null,
        discipline: asText(row.getCell(2).value) || null,
        supplier: asText(row.getCell(4).value) || null,
        area: asText(row.getCell(5).value) || null,
        responsible: asText(row.getCell(6).value) || null,
        startupAt: lineStartup,
        suppliesDays: days(row.getCell(11).value, `${location} (Suprimentos)`, warnings),
        legalDays: days(row.getCell(12).value, `${location} (Jurídico)`, warnings),
        manufactureDays: days(row.getCell(13).value, `${location} (Fabricação)`, warnings),
        preStartDays: days(row.getCell(14).value, `${location} (Antecedência)`, warnings),
      });
    }
    if (!startup || !items.length) throw new Error(`A aba ${sheet.name} não contém startup/equipamentos válidos.`);
    // Datas iguais à referência devem herdar a data do cenário para permitir deslocar tudo.
    for (const row of items) {
      if (!row.startupAt || row.startupAt === startup) row.startupAt = null;
    }
    scenarios.push({
      name: `Startup ${match[1]}`, startupAt: startup, items,
    });
  }
  if (!scenarios.length) {
    throw new Error("Não encontrei as abas PLAN EQUIPAMENTOS ... 2027/2028 no arquivo.");
  }
  return { scenarios, warnings };
}
