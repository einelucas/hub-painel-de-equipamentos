import { computed, getCurrentInstance, nextTick, onBeforeUnmount, ref, watch, type Ref } from "vue";

/**
 * Renderização incremental de listas grandes: mostra um lote inicial e acrescenta
 * o próximo quando o sentinela (dentro do contêiner rolável) se aproxima da vista.
 * Volta ao primeiro lote sempre que a lista de origem é substituída.
 */
export function useIncrementalList<T>(source: () => readonly T[], options: { batchSize?: number } = {}) {
  const batchSize = options.batchSize ?? 50;
  const count = ref(batchSize);
  const root: Ref<HTMLElement | null> = ref(null);
  const sentinel: Ref<HTMLElement | null> = ref(null);
  let observer: IntersectionObserver | null = null;

  const total = computed(() => source().length);
  const visible = computed(() => source().slice(0, count.value));
  const hasMore = computed(() => count.value < total.value);

  function loadMore(): void {
    if (hasMore.value) count.value = Math.min(count.value + batchSize, total.value);
  }

  function reset(): void {
    count.value = batchSize;
    if (root.value) root.value.scrollTop = 0;
  }

  function disconnect(): void {
    observer?.disconnect();
    observer = null;
  }

  function connect(): void {
    disconnect();
    if (!sentinel.value || typeof IntersectionObserver === "undefined") return;
    observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) loadMore();
      },
      { root: root.value, rootMargin: "0px 0px 240px 0px" },
    );
    observer.observe(sentinel.value);
  }

  watch(source, reset);
  watch([root, sentinel], connect, { flush: "post" });
  // Se o sentinela continuar visível após acrescentar, reobserva para disparar de novo.
  watch(count, async () => {
    await nextTick();
    connect();
  });
  if (getCurrentInstance()) onBeforeUnmount(disconnect);

  return { root, sentinel, visible, total, hasMore, loadMore, reset };
}
