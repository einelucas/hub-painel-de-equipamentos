import { describe, expect, it, vi } from "vitest";
import { useAsyncAction } from "~/composables/useAsyncAction";

describe("useAsyncAction", () => {
  it("marca pending durante a execução e ignora chamadas duplicadas", async () => {
    let resolve!: (v: string) => void;
    const fn = vi.fn(() => new Promise<string>((r) => { resolve = r; }));
    const { pending, run } = useAsyncAction(fn);
    const first = run();
    expect(pending.value).toBe(true);
    expect(await run()).toBeUndefined();
    expect(fn).toHaveBeenCalledTimes(1);
    resolve("ok");
    expect(await first).toBe("ok");
    expect(pending.value).toBe(false);
  });

  it("repassa argumentos, relança erros e reseta pending", async () => {
    const fn = vi.fn(async (n: number) => { if (n < 0) throw new Error("boom"); return n; });
    const { pending, run } = useAsyncAction(fn);
    expect(await run(2)).toBe(2);
    await expect(run(-1)).rejects.toThrow("boom");
    expect(pending.value).toBe(false);
    expect(await run(3)).toBe(3);
  });
});
