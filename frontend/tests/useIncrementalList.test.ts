import { describe, expect, it } from "vitest";
import { nextTick, ref } from "vue";
import { useIncrementalList } from "~/composables/useIncrementalList";

const make = (n: number) => Array.from({ length: n }, (_, i) => i);

describe("useIncrementalList", () => {
  it("renderiza apenas o lote inicial", () => {
    const list = useIncrementalList(() => make(120), { batchSize: 50 });
    expect(list.visible.value).toHaveLength(50);
    expect(list.total.value).toBe(120);
    expect(list.hasMore.value).toBe(true);
  });

  it("loadMore acrescenta lotes até o total", () => {
    const list = useIncrementalList(() => make(120), { batchSize: 50 });
    list.loadMore();
    expect(list.visible.value).toHaveLength(100);
    list.loadMore();
    expect(list.visible.value).toHaveLength(120);
    expect(list.hasMore.value).toBe(false);
    list.loadMore();
    expect(list.visible.value).toHaveLength(120);
  });

  it("volta ao primeiro lote quando a origem muda", async () => {
    const source = ref(make(120));
    const list = useIncrementalList(() => source.value, { batchSize: 50 });
    list.loadMore();
    source.value = make(80);
    await nextTick();
    expect(list.visible.value).toHaveLength(50);
  });

  it("lista curta não tem mais itens a carregar", () => {
    const list = useIncrementalList(() => make(3));
    expect(list.visible.value).toHaveLength(3);
    expect(list.hasMore.value).toBe(false);
  });
});
