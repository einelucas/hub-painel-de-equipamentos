import { describe, expect, it } from "vitest";
import { formatDateOnly, formatDateTime, formatNumber } from "~/utils/format";

describe("formatNumber", () => {
  it("formata números no padrão pt-BR", () => {
    expect(formatNumber(1234.5, 1)).toBe("1.234,5");
  });
});

describe("formatDateOnly (Etapa 6C: bug de timezone em datas DATE-ONLY)", () => {
  it("preserva exatamente o dia recebido da API, sem deslocar por timezone", () => {
    // Regressão do bug reportado: API "2027-10-26" não pode virar "25/10/2027".
    expect(formatDateOnly("2027-10-26")).toBe("26/10/2027");
  });

  it("funciona em datas de início/fim de mês e ano", () => {
    expect(formatDateOnly("2027-01-01")).toBe("01/01/2027");
    expect(formatDateOnly("2026-12-31")).toBe("31/12/2026");
  });

  it("funciona em 29 de fevereiro de ano bissexto", () => {
    expect(formatDateOnly("2028-02-29")).toBe("29/02/2028");
  });

  it("ignora a parte de hora/timezone se vier junto (mantém o dia)", () => {
    expect(formatDateOnly("2027-10-26T00:00:00.000Z")).toBe("26/10/2027");
  });

  it("devolve travessão para valores vazios", () => {
    expect(formatDateOnly(null)).toBe("—");
    expect(formatDateOnly(undefined)).toBe("—");
    expect(formatDateOnly("")).toBe("—");
  });

  it("devolve o texto original para algo que não é uma data válida", () => {
    expect(formatDateOnly("não é data")).toBe("não é data");
  });
});

describe("formatDateTime (Etapa 6C)", () => {
  it("formata data e hora de um timestamp completo", () => {
    const result = formatDateTime("2026-09-21T14:30:00.000Z");
    // Só garante que tem os dois pedaços (data + hora) — o valor exato de
    // hora depende do fuso do ambiente de teste, e isso é o comportamento
    // correto para DATETIME (ao contrário de DATE-ONLY).
    expect(result).toMatch(/\d{2}\/\d{2}\/\d{4}/);
    expect(result).toMatch(/\d{2}:\d{2}/);
  });

  it("devolve travessão para valores vazios", () => {
    expect(formatDateTime(null)).toBe("—");
  });
});
