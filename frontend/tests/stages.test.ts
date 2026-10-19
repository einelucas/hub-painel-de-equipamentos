import { describe, expect, it } from "vitest";
import {
  STAGE_CANCELLED_COLOR,
  STAGE_COLORS,
  STAGE_FALLBACK_COLOR,
  stageBadgeStyle,
  stageColor,
  withAlpha,
} from "~/utils/stages";

describe("stageColor", () => {
  it("usa a cor oficial de cada fase de 0 a 8", () => {
    expect(stageColor(0)).toBe("#a8bde7");
    expect(stageColor(1)).toBe("#349ecd");
    expect(stageColor(2)).toBe("#fdbc64");
    expect(stageColor(3)).toBe("#936fdb");
    expect(stageColor(4)).toBe("#349970");
    expect(stageColor(5)).toBe("#ff7bf0");
    expect(stageColor(6)).toBe("#79affd");
    expect(stageColor(7)).toBe("#ff8358");
    expect(stageColor(8)).toBe("#32f491");
  });

  it("define uma cor para cada fase cadastrada", () => {
    expect(Object.keys(STAGE_COLORS)).toHaveLength(9);
  });

  it("cai no amarelo nas demais fases", () => {
    expect(stageColor(9)).toBe(STAGE_FALLBACK_COLOR);
    expect(stageColor(-1)).toBe(STAGE_FALLBACK_COLOR);
  });

  it("usa vermelho quando a etapa indica cancelamento", () => {
    expect(stageColor(3, "Cancelado")).toBe(STAGE_CANCELLED_COLOR);
    expect(stageColor(3, "Cancelada")).toBe(STAGE_CANCELLED_COLOR);
    expect(stageColor(3, "Aprovação da minuta")).toBe("#936fdb");
  });
});

describe("withAlpha", () => {
  it("converte a cor com alfa para rgba", () => {
    expect(withAlpha("#ff8358", 0.25)).toBe("rgba(255, 131, 88, 0.25)");
  });
});

describe("stageBadgeStyle", () => {
  it("aplica a cor da fase com o mesmo alfa dos outros badges", () => {
    expect(stageBadgeStyle(7)).toEqual({
      backgroundColor: "rgba(255, 131, 88, 0.25)",
      color: "#263b59",
    });
  });

  it("respeita o amarelo de fallback e o vermelho de cancelado", () => {
    expect(stageBadgeStyle(42).backgroundColor).toBe(withAlpha(STAGE_FALLBACK_COLOR, 0.25));
    expect(stageBadgeStyle(1, "Cancelado").backgroundColor).toBe(withAlpha(STAGE_CANCELLED_COLOR, 0.25));
  });
});
