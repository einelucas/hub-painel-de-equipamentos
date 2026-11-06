import { describe, expect, it } from "vitest";
import {
  dateUtc,
  eapNameLabel,
  hasDistributionData,
  hasEapStageData,
  hasRiskData,
  inclusiveRange,
  monthCaption,
  safeNumber,
  shortEapLabel,
  visibleTop,
} from "~/utils/dashboardAnalytics";

describe("dashboard analytics", () => {
  it("mantém códigos EAP, inclusive os não classificados", () => {
    expect(shortEapLabel("01.A · Caldeira")).toBe("01.A");
    expect(shortEapLabel("Sem EAP")).toBe("Sem EAP");
  });

  it("separa o nome da EAP do código do badge", () => {
    expect(eapNameLabel("01.A · Caldeira")).toBe("Caldeira");
    expect(eapNameLabel("Sem EAP")).toBe("Sem EAP");
  });

  it("não transforma valores inválidos em números não finitos", () => {
    expect(safeNumber("123.45")).toBe(123.45);
    expect(safeNumber("inválido")).toBe(0);
    expect(monthCaption("2026-11")).toBe("11/26");
  });

  it("limita visualização explicitando quantas categorias foram ocultadas", () => {
    expect(visibleTop([1, 2, 3, 4], 2)).toEqual({ visible: [1, 2], omitted: 2 });
  });

  it("trata datas contratuais como dias inclusivos em UTC", () => {
    const [start, end] = inclusiveRange("2026-11-05", "2026-11-05");
    expect(start).toBe(dateUtc("2026-11-05"));
    expect(end - start).toBe(86_400_000);
  });

  it("distingue séries vazias de risco não calculável", () => {
    expect(hasDistributionData([{ id: null, label: "Sem classificação", count: 0 }])).toBe(false);
    expect(hasEapStageData([{ eapId: null, label: "Sem EAP", total: 1, counts: [1, 0, 0, 0, 0, 0, 0, 0, 0] }])).toBe(true);
    expect(hasRiskData([{ eapId: null, label: "Sem EAP", critical: 0, warning: 0, safe: 0, notCalculable: 3 }])).toBe(false);
  });
});
