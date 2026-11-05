import { describe, expect, it } from "vitest";
import { matchesSearchText, normalizeSearchText } from "~/utils/search";

describe("busca sem acentos", () => {
  it("normaliza acentos e caixa", () => {
    expect(normalizeSearchText("Incêndio")).toBe("incendio");
    expect(normalizeSearchText("ÁREA")).toBe("area");
    expect(normalizeSearchText("Elétrica")).toBe("eletrica");
  });

  it("encontra nomes acentuados digitando sem acento", () => {
    expect(matchesSearchText("Sistema contra incêndios", "incendio")).toBe(true);
    expect(matchesSearchText("Sistema contra incêndios", "INCÊNDIO")).toBe(true);
    expect(matchesSearchText("Sistema de Combate a Incêndio", "combate a incendio")).toBe(true);
    expect(matchesSearchText("Mecânica", "mecanica")).toBe(true);
  });

  it("continua exigindo que o texto exista no nome", () => {
    expect(matchesSearchText("Hidráulica", "eletrica")).toBe(false);
    expect(matchesSearchText("Incêndio", "incendios")).toBe(false);
  });
});
