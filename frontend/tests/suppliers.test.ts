import { describe, expect, it } from "vitest";
import { cnpjStatus, formatCnpj, maskCnpjInput, normalizeCnpj, sortSuppliers, supplierLabel } from "~/utils/suppliers";

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

  it("mascara o CNPJ enquanto se digita e preserva texto não numérico", () => {
    expect(maskCnpjInput("1234")).toBe("12.34");
    expect(maskCnpjInput("12345678")).toBe("12.345.678");
    expect(maskCnpjInput("123456780001")).toBe("12.345.678/0001");
    expect(maskCnpjInput("1234567800019599")).toBe("12.345.678/0001-95");
    expect(maskCnpjInput("12.345.678/0001-95")).toBe("12.345.678/0001-95");
    expect(maskCnpjInput("PASSPORT 123")).toBe("PASSPORT 123");
  });

  it("confere os dígitos verificadores do CNPJ", () => {
    expect(cnpjStatus("")).toBe("empty");
    expect(cnpjStatus("12.345.678")).toBe("incomplete");
    expect(cnpjStatus("11.222.333/0001-81")).toBe("valid");
    expect(cnpjStatus("11222333000181")).toBe("valid");
    expect(cnpjStatus("11.222.333/0001-80")).toBe("invalid");
    expect(cnpjStatus("00000000000000")).toBe("invalid");
    expect(cnpjStatus("documento estrangeiro")).toBe("other");
  });
});
