export function formatNumber(value: unknown, maximumFractionDigits = 2): string {
  const number = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(number)) return "—";
  return new Intl.NumberFormat("pt-BR", { maximumFractionDigits }).format(number);
}

export function formatPercent(value: unknown, fraction = false): string {
  const number = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(number)) return "—";
  return `${formatNumber(fraction ? number * 100 : number, 1)}%`;
}

export function formatCurrency(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  const number = Number(value);
  if (!Number.isFinite(number)) return "—";
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(number);
}

const _DATE_ONLY_PATTERN = /^(\d{4})-(\d{2})-(\d{2})/;

/**
 * Campos DATE-ONLY da API (ex.: `startupAt`, `negotiatedAt`, os prazos
 * calculados na Etapa 6B) — sempre `YYYY-MM-DD`, sem hora nem timezone.
 *
 * `new Date("2027-10-26")` é interpretado pelo JS como meia-noite **UTC**;
 * formatar isso de volta no fuso local do navegador pode exibir o dia
 * anterior (ex.: `25/10/2027` em vez de `26/10/2027`) dependendo do fuso.
 * Esta função nunca passa pelo parser de string do `Date`: extrai
 * ano/mês/dia do texto e monta a data com o construtor numérico
 * (`new Date(ano, mês, dia)`), que é sempre interpretado no fuso LOCAL —
 * não há conversão de fuso nenhuma para dar errado. O dia exibido é sempre
 * exatamente o dia recebido da API, em qualquer fuso do navegador.
 */
export function formatDateOnly(value: unknown): string {
  if (!value) return "—";
  const match = _DATE_ONLY_PATTERN.exec(String(value));
  if (!match) return String(value);
  const [, year, month, day] = match;
  const date = new Date(Number(year), Number(month) - 1, Number(day));
  if (Number.isNaN(date.getTime())) return String(value);
  return new Intl.DateTimeFormat("pt-BR", { dateStyle: "short" }).format(date);
}

/**
 * Campos DATETIME da API (ex.: `createdAt`, `updatedAt`, `occurredAt` de
 * AuditLog/WorkflowTransition) — timestamp completo, com hora real que faz
 * sentido converter para o fuso do navegador (é exatamente para isso que
 * serve mostrar hora: "quando isso aconteceu, no meu fuso").
 */
export function formatDateTime(value: unknown): string {
  if (!value) return "—";
  const date = new Date(String(value));
  if (Number.isNaN(date.getTime())) return String(value);
  return new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" }).format(date);
}

export function getPath(source: unknown, path: string): unknown {
  return path.split(".").reduce<unknown>((current, key) => {
    if (current && typeof current === "object") return (current as Record<string, unknown>)[key];
    return undefined;
  }, source);
}
