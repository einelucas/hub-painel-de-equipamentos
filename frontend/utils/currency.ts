const BRL_FORMATTER = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

/**
 * Converte o texto digitado em um decimal com duas casas (ponto decimal).
 *
 * Aceita o formato brasileiro (`1.234,56`), o decimal da API (`1234.56`) e
 * valores inteiros. Letras e outros símbolos são descartados. O retorno vazio
 * representa "sem valor", diferente de zero.
 */
export function parseCurrencyInput(raw: string): string {
  const cleaned = raw.replace(/[^\d,.]/g, "");
  if (!cleaned) return "";

  const lastComma = cleaned.lastIndexOf(",");
  let normalized: string;

  if (lastComma >= 0) {
    const integer = cleaned.slice(0, lastComma).replace(/\D/g, "") || "0";
    const decimals = cleaned.slice(lastComma + 1).replace(/\D/g, "").slice(0, 2);
    normalized = `${integer}.${decimals || "0"}`;
  } else {
    const lastDot = cleaned.lastIndexOf(".");
    const afterDot = lastDot >= 0 ? cleaned.slice(lastDot + 1) : "";
    if (lastDot >= 0 && /^\d{1,2}$/.test(afterDot)) {
      const integer = cleaned.slice(0, lastDot).replace(/\D/g, "") || "0";
      normalized = `${integer}.${afterDot}`;
    } else {
      const integer = cleaned.replace(/\D/g, "") || "0";
      normalized = `${integer}.0`;
    }
  }

  const number = Number(normalized);
  if (!Number.isFinite(number) || number < 0) return "";
  return number.toFixed(2);
}

/** Formata um valor da API para exibição no campo, incluindo o símbolo R$. */
export function formatCurrencyInput(value: string | number | null | undefined): string {
  if (value === null || value === undefined) return "";
  const normalized = parseCurrencyInput(String(value));
  return normalized ? BRL_FORMATTER.format(Number(normalized)) : "";
}

/** Valor sem separador de milhar, usado enquanto o campo está em edição. */
export function editableCurrencyInput(value: string | number | null | undefined): string {
  if (value === null || value === undefined) return "";
  const normalized = parseCurrencyInput(String(value));
  return normalized ? normalized.replace(".", ",") : "";
}
