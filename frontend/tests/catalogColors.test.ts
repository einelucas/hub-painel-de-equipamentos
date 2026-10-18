import { describe, expect, it } from "vitest";
import {
  CATALOG_FALLBACK_COLOR,
  catalogColor,
  criticalityColor,
  disciplineColor,
  translucentBadgeStyle,
} from "~/utils/catalogColors";

describe("catalogColor", () => {
  it("usa sempre a cor cadastrada no banco", () => {
    expect(disciplineColor({ id: "d-1", name: "Civil", code: "CIV", color: "#123456" })).toBe("#123456");
    expect(criticalityColor("#abcdef")).toBe("#abcdef");
  });

  it("ignora o código da disciplina no cálculo da cor", () => {
    // Antes o código alimentava um mapa fixo no frontend; agora dois itens com o
    // mesmo código podem ter cores diferentes, porque a fonte é o catálogo.
    const primeira = disciplineColor({ id: "d-1", name: "Civil", code: "CIV", color: "#111111" });
    const segunda = disciplineColor({ id: "d-2", name: "Civil", code: "CIV", color: "#222222" });

    expect(primeira).toBe("#111111");
    expect(segunda).toBe("#222222");
  });

  it("cai no cinza neutro quando o item ainda não tem cor no catálogo", () => {
    expect(disciplineColor({ id: "d-1", name: "Disciplina nova", code: "NOVA" })).toBe(CATALOG_FALLBACK_COLOR);
    expect(catalogColor(null)).toBe(CATALOG_FALLBACK_COLOR);
    expect(catalogColor("")).toBe(CATALOG_FALLBACK_COLOR);
    expect(catalogColor(undefined)).toBe(CATALOG_FALLBACK_COLOR);
  });
});

describe("translucentBadgeStyle", () => {
  it("deriva fundo e borda translúcidos a partir da cor", () => {
    expect(translucentBadgeStyle("#123456")).toEqual({
      "--badge-color": "#123456",
      "--badge-background": "#12345667",
      "--badge-border": "#12345652",
    });
  });
});
