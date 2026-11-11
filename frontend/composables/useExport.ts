import { jsPDF } from "jspdf";
import autoTable from "jspdf-autotable";
import type { Equipment } from "~/types/equipment";

export function useExport() {
  async function excel(fileName: string, equipments: Equipment[]): Promise<void> {
    const { downloadEquipmentWorkbook } = await import(
      "~/utils/equipmentExcelExport"
    );
    await downloadEquipmentWorkbook(fileName, equipments);
  }

  function pdf(fileName: string, title: string, rows: Array<Record<string, unknown>>) {
    const document = new jsPDF({ orientation: rows.length && Object.keys(rows[0]!).length > 6 ? "landscape" : "portrait" });
    document.setFontSize(16);
    document.setTextColor(33, 55, 88);
    document.text(title, 14, 16);
    const columns = rows.length ? Object.keys(rows[0]!) : ["mensagem"];
    const body = rows.length ? rows.map(row => columns.map(column => String(row[column] ?? "—"))) : [["Sem dados"]];
    autoTable(document, { head: [columns], body, startY: 23, styles: { fontSize: 7 }, headStyles: { fillColor: [48, 79, 126] } });
    document.save(fileName.endsWith(".pdf") ? fileName : `${fileName}.pdf`);
  }

  return { excel, pdf };
}
