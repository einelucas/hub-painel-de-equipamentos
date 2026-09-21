import { describe, expect, it } from "vitest";
import type { NegotiationStatus } from "~/types/equipment";
import { negotiationStatusLabel, negotiationStatusTone } from "~/utils/negotiationStatus";

describe("negotiationStatusLabel (GAP-014 — só apresentação, sem recalcular threshold)", () => {
  const cases: Array<[NegotiationStatus, string]> = [
    ["OVERDUE", "Atrasado"],
    ["DUE_TODAY", "Vence hoje"],
    ["CRITICAL", "Crítico"],
    ["URGENT", "Urgente"],
    ["UPCOMING", "Próximo"],
    ["ON_TRACK", "No prazo"],
    ["COMPLETED", "Concluído"],
    ["NOT_APPLICABLE", "Não se aplica"],
  ];

  it.each(cases)("traduz %s para %s", (status, label) => {
    expect(negotiationStatusLabel(status)).toBe(label);
  });

  it("devolve travessão quando não há status (deadline e negotiatedAt ausentes)", () => {
    expect(negotiationStatusLabel(null)).toBe("—");
  });

  it("cada status tem um tom associado (não quebra em nenhum valor)", () => {
    for (const [status] of cases) {
      expect(negotiationStatusTone(status)).toMatch(/^negotiation-badge--/);
    }
    expect(negotiationStatusTone(null)).toBe("negotiation-badge--neutral");
  });
});
