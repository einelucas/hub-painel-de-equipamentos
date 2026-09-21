import { describe, expect, it } from "vitest";
import type { WorkNeedStatus } from "~/types/equipment";
import { workNeedStatusLabel, workNeedStatusTone } from "~/utils/workNeedStatus";

describe("workNeedStatusLabel (Etapa 6C.1 — só apresentação, sem recalcular threshold)", () => {
  const cases: Array<[WorkNeedStatus, string]> = [
    ["CHECK_DELIVERY_FUP", "Checar entrega/FUP"],
    ["NEEDED_TODAY", "Necessita hoje"],
    ["LT_30_DAYS", "< 30 dias"],
    ["LT_60_DAYS", "< 60 dias"],
    ["LT_90_DAYS", "< 90 dias"],
    ["SAFE", "Prazo seguro"],
  ];

  it.each(cases)("traduz %s para %s", (status, label) => {
    expect(workNeedStatusLabel(status)).toBe(label);
  });

  it("devolve travessão quando não há deliveryDeadline", () => {
    expect(workNeedStatusLabel(null)).toBe("—");
  });

  it("cada status tem um tom associado (não quebra em nenhum valor)", () => {
    for (const [status] of cases) {
      expect(workNeedStatusTone(status)).toMatch(/^negotiation-badge--/);
    }
    expect(workNeedStatusTone(null)).toBe("negotiation-badge--neutral");
  });
});
