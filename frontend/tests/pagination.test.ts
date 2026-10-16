import { describe, expect, it, vi } from "vitest";
import { collectAllPages } from "~/utils/pagination";

describe("collectAllPages", () => {
  it("não corta conjuntos acima de 2.000 registros", async () => {
    const load = vi.fn(async (page: number) => ({
      items: Array.from({ length: page === 21 ? 5 : 100 }, (_, index) => (page - 1) * 100 + index),
      pagination: { page, pageSize: 100, total: 2005, totalPages: 21 },
    }));

    const result = await collectAllPages(load);

    expect(result).toHaveLength(2005);
    expect(load).toHaveBeenCalledTimes(21);
  });

  it("falha explicitamente se o total de páginas mudar", async () => {
    await expect(collectAllPages(async (page) => ({
      items: [page],
      pagination: { page, pageSize: 1, total: 2, totalPages: page === 1 ? 2 : 3 },
    }))).rejects.toThrow("mudaram durante o carregamento");
  });
});
