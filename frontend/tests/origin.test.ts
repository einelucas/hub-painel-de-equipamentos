import { describe, expect, it } from "vitest";
import { DEFAULT_ORIGIN, ORIGIN_OPTIONS, originOptions } from "~/utils/origin";

describe("origem do equipamento", () => {
  it("oferece o vocabulário fechado do domínio", () => {
    expect(ORIGIN_OPTIONS).toEqual(["Nacional", "Internacional", "A definir"]);
    expect(ORIGIN_OPTIONS).toContain(DEFAULT_ORIGIN);
  });

  it("acrescenta o valor atual quando ele está fora do vocabulário", () => {
    expect(originOptions("Importado")).toEqual([
      "Nacional",
      "Internacional",
      "A definir",
      "Importado",
    ]);
  });

  it("não repete valores que já pertencem ao vocabulário", () => {
    expect(originOptions("Nacional")).toEqual(["Nacional", "Internacional", "A definir"]);
    expect(originOptions(null)).toEqual(["Nacional", "Internacional", "A definir"]);
    expect(originOptions("   ")).toEqual(["Nacional", "Internacional", "A definir"]);
  });
});
