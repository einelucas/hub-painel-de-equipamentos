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
