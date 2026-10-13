import type { Supplier } from "~/types/equipment";

export function supplierLabel(supplier: Pick<Supplier, "corporateCode" | "legalName">): string {
  return supplier.corporateCode
    ? `${supplier.corporateCode} · ${supplier.legalName}`
    : supplier.legalName;
}

export function sortSuppliers<T extends Pick<Supplier, "corporateCode" | "legalName">>(
  suppliers: T[],
): T[] {
  return [...suppliers].sort((left, right) => {
    const byName = left.legalName.localeCompare(right.legalName, "pt-BR", {
      sensitivity: "base",
    });
    if (byName !== 0) return byName;
    return (left.corporateCode ?? "").localeCompare(right.corporateCode ?? "", "pt-BR", {
      numeric: true,
      sensitivity: "base",
    });
  });
}

export function formatCnpj(value: string | null | undefined): string {
  if (!value?.trim()) return "—";
  const trimmed = value.trim();
  const digits = trimmed.replace(/\D/g, "");
  if (digits.length !== 14) return trimmed;
  return digits.replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, "$1.$2.$3/$4-$5");
}

export function normalizeCnpj(value: string): string | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  const digits = trimmed.replace(/\D/g, "");
  return digits.length === 14 ? digits : trimmed;
}

/**
 * Máscara enquanto se digita: só reformata entradas numéricas (com ou sem
 * pontuação de CNPJ); qualquer outro texto (ex.: documento estrangeiro) fica intacto.
 */
export function maskCnpjInput(value: string): string {
  if (/[^\d./\-\s]/.test(value)) return value;
  const digits = value.replace(/\D/g, "").slice(0, 14);
  const parts = [digits.slice(0, 2), digits.slice(2, 5), digits.slice(5, 8), digits.slice(8, 12), digits.slice(12, 14)];
  let masked = parts[0]!;
  if (parts[1]) masked += `.${parts[1]}`;
  if (parts[2]) masked += `.${parts[2]}`;
  if (parts[3]) masked += `/${parts[3]}`;
  if (parts[4]) masked += `-${parts[4]}`;
  return masked;
}

export type CnpjStatus = "empty" | "incomplete" | "valid" | "invalid" | "other";

/** Situação do documento para orientar o preenchimento (não bloqueia o cadastro). */
export function cnpjStatus(value: string | null | undefined): CnpjStatus {
  const trimmed = value?.trim() ?? "";
  if (!trimmed) return "empty";
  if (/[^\d./\-\s]/.test(trimmed)) return "other";
  const digits = trimmed.replace(/\D/g, "");
  if (digits.length < 14) return "incomplete";
  if (digits.length > 14 || /^(\d)\1{13}$/.test(digits)) return "invalid";
  const check = (base: string, weights: number[]): number => {
    const sum = weights.reduce((total, weight, index) => total + Number(base[index]) * weight, 0);
    const rest = sum % 11;
    return rest < 2 ? 0 : 11 - rest;
  };
  const first = check(digits, [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]);
  const second = check(digits, [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]);
  return digits.endsWith(`${first}${second}`) ? "valid" : "invalid";
}
