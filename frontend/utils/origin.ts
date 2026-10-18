/**
 * Origem do equipamento.
 *
 * Diferente de disciplinas e criticidades (catálogos com cor no banco), a
 * origem é uma lista fechada do domínio: a edição no Hub é sempre uma destas
 * opções, nunca texto livre.
 */
export const ORIGIN_OPTIONS = ["Nacional", "Internacional", "A definir"] as const;

/** Valor padrão de quem ainda não decidiu — e o mesmo texto já usado nos dados. */
export const DEFAULT_ORIGIN = "A definir";

/**
 * Opções do select de origem.
 *
 * Registros antigos podem carregar um valor fora do vocabulário (ex.:
 * "Importado", texto que veio da planilha do Monday). Nesse caso ele é
 * acrescentado à lista para que o select mostre o dado real do equipamento em
 * vez de aparecer vazio — ninguém consegue *escolher* esse valor em um
 * registro novo, só mantê-lo ou trocar por uma das opções do domínio.
 */
export function originOptions(current?: string | null): string[] {
  const options: string[] = [...ORIGIN_OPTIONS];
  const value = current?.trim();
  if (value && !options.includes(value)) {
    options.push(value);
  }
  return options;
}
