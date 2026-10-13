import { describe, expect, it, vi } from "vitest";
import { loadEapLocationOptions } from "~/utils/eapLocationOptions";
import type { EapNodeItem } from "~/types/equipment";

function node(overrides: Partial<EapNodeItem>): EapNodeItem {
  return {
    id: "n",
    code: "00",
    name: "Nó",
    level: "AREA",
    parentId: null,
    active: true,
    createdAt: "2026-01-01T00:00:00Z",
    updatedAt: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

describe("loadEapLocationOptions", () => {
  it("usa a EAP (Processo/Área ativos), ordenada por código, no formato código · nome", async () => {
    const get = vi.fn().mockResolvedValue({
      items: [
        node({ id: "a10", code: "04.10", name: "Pátio" }),
        node({ id: "ilha", code: "04", name: "Ilha", level: "ISLAND" }),
        node({ id: "a2", code: "04.2", name: "Casa de Força" }),
        node({ id: "p1", code: "03", name: "Caldeira", level: "PROCESS" }),
        node({ id: "off", code: "01", name: "Inativo", active: false }),
      ],
    });

    const options = await loadEapLocationOptions({ get } as never);

    expect(get).toHaveBeenCalledWith("/eap-nodes", { active: true });
    expect(options.map((item) => [item.id, item.name])).toEqual([
      ["p1", "03 · Caldeira"],
      ["a2", "04.2 · Casa de Força"],
      ["a10", "04.10 · Pátio"],
    ]);
  });
});
