export interface PaginatedResult<T> {
  items: T[];
  pagination: {
    page: number;
    pageSize: number;
    total: number;
    totalPages: number;
  };
}

/**
 * Carrega todas as páginas anunciadas pela API. O limite é uma proteção contra
 * respostas inconsistentes, não um corte silencioso: ao atingi-lo, a operação
 * falha para que o usuário saiba que o conjunto ficou incompleto.
 */
export async function collectAllPages<T>(
  loadPage: (page: number) => Promise<PaginatedResult<T>>,
  options: { maxPages?: number; onProgress?: (page: number, totalPages: number) => void } = {},
): Promise<T[]> {
  const maxPages = options.maxPages ?? 10_000;
  const items: T[] = [];
  let expectedPages: number | null = null;

  for (let page = 1; ; page += 1) {
    const result = await loadPage(page);
    const totalPages = result.pagination.totalPages;
    if (!Number.isInteger(totalPages) || totalPages < 0 || totalPages > maxPages) {
      throw new Error("A API informou uma paginação inválida; nenhum resultado parcial foi usado.");
    }
    if (expectedPages !== null && totalPages !== expectedPages) {
      throw new Error("Os registros mudaram durante o carregamento; tente novamente.");
    }
    expectedPages = totalPages;
    items.push(...result.items);
    options.onProgress?.(page, totalPages);
    if (page >= totalPages) return items;
  }
}
