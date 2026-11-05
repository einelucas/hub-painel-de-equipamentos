/**
 * Normalização de texto para buscas do Hub.
 *
 * A busca ignora acentos e diferenças entre maiúsculas e minúsculas, para que
 * `incendio` encontre `Incêndio` e `INCÊNDIO`. A normalização fica
 * centralizada aqui e é usada tanto pelos filtros client-side quanto como
 * referência de comportamento dos campos do Vuetify (`ignoreAccents`).
 */

/** Remove acentos e converte o texto para minúsculas. */
export function normalizeSearchText(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("pt-BR");
}

/** Verifica se `haystack` contém `needle`, ignorando acentos e caixa. */
export function matchesSearchText(haystack: string, needle: string): boolean {
  return normalizeSearchText(haystack).includes(normalizeSearchText(needle));
}
