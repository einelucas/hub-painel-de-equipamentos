import { ref } from "vue";

/** Envolve uma função assíncrona com estado `pending` e guarda contra execução duplicada. */
export function useAsyncAction<A extends unknown[], R>(fn: (...args: A) => Promise<R>) {
  const pending = ref(false);

  async function run(...args: A): Promise<R | undefined> {
    if (pending.value) return undefined;
    pending.value = true;
    try {
      return await fn(...args);
    } finally {
      pending.value = false;
    }
  }

  return { pending, run };
}
