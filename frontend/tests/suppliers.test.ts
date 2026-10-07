import { describe, expect, it } from "vitest";
import { formatCnpj, normalizeCnpj, sortSuppliers, supplierLabel } from "~/utils/suppliers";

describe("fornecedores", () => {
  it("ordena por razão social e mantém código no rótulo", () => {
    const suppliers = sortSuppliers([
      { legalName: "Zeta Industrial", corporateCode: "20" },
      { legalName: "Águas Serviços", corporateCode: "10" },
      { legalName: "Beta Engenharia", corporateCode: null },
    ]);

    expect(suppliers.map((item) => item.legalName)).toEqual([
      "Águas Serviços",
      "Beta Engenharia",
      "Zeta Industrial",
    ]);
    expect(supplierLabel(suppliers[0]!)).toBe("10 · Águas Serviços");
  });

  it("reconhece CNPJ numérico, formata a exibição e normaliza o envio", () => {
    expect(formatCnpj("12345678000195")).toBe("12.345.678/0001-95");
    expect(formatCnpj("12.345.678/0001-95")).toBe("12.345.678/0001-95");
    expect(normalizeCnpj("12.345.678/0001-95")).toBe("12345678000195");
    expect(formatCnpj("documento estrangeiro")).toBe("documento estrangeiro");
  });
});
