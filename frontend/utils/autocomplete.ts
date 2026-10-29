import type { SearchableOption } from "~/types/ui";

/**
 * Bridge entre as opções do Hub (`SearchableOption`) e os itens do
 * `v-autocomplete` do Vuetify.
 *
 * Os seletores do app usam o `v-autocomplete` direto (padrão Vuetify);
 * estas helpers centralizam só o mapeamento de dados, para que cada chamada
 * fique parecida com a documentação: `:items="toAutocompleteItems(options)"`.
 */

export interface AutocompleteItem {
  /** Rótulo visível (equivalente ao `label` antigo). */
  title: string;
  /** Valor do modelo (equivalente ao `id` antigo; `""` para a opção vazia). */
  value: string;
  /** Texto extra de busca (títulos alternativos, tags etc.) — nunca exibido. */
  searchText?: string;
  /** Props extras do `VListItem`, ex. `subtitle` (equivale à `description`). */
  props?: { subtitle?: string };
}

export interface AutocompleteItemsOptions {
  /** Primeira opção vazia do menu, ex. `"Não informado"` / `"Todas as áreas"`. */
  emptyLabel?: string;
  /** Valor da opção vazia (padrão `""`). */
  emptyValue?: string;
  /** Ordena por título com regra pt-BR; `false` preserva a ordem (ex.: etapas 0–8). */
  sorted?: boolean;
}

function sortByLabel(options: SearchableOption[]): SearchableOption[] {
  return [...options].sort((left, right) =>
    left.label.localeCompare(right.label, "pt-BR", {
      numeric: true,
      sensitivity: "base",
    }),
  );
}

/**
 * Converte `SearchableOption[]` em itens do `v-autocomplete`.
 * O valor permanece `string` (como antes), e rótulos/ids não mudam.
 */
export function toAutocompleteItems(
  options: readonly SearchableOption[],
  extra?: AutocompleteItemsOptions,
): AutocompleteItem[] {
  const emptyLabel = extra?.emptyLabel ?? "";
  const emptyValue = extra?.emptyValue ?? "";
  const source = extra?.sorted === false ? [...options] : sortByLabel([...options]);

  const items: AutocompleteItem[] = source.map((option) => ({
    title: option.label,
    value: option.id,
    ...(option.searchText ? { searchText: option.searchText } : {}),
    ...(option.description ? { props: { subtitle: option.description } } : {}),
  }));

  return emptyLabel
    ? [{ title: emptyLabel, value: emptyValue, searchText: emptyLabel }, ...items]
    : items;
}

/**
 * Chaves usadas pelo `v-autocomplete`/`v-select` ao filtrar o que o usuário
 * digita: título, `searchText` e o subtítulo (`props.subtitle`), igual ao
 * comportamento do `SearchableSelect` anterior.
 */
export const AUTOCOMPLETE_FILTER_KEYS = [
  "title",
  "searchText",
  "props.subtitle",
] as const;
