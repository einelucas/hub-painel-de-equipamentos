import { mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import EapTreeAdmin from "~/components/admin/EapTreeAdmin.vue";

const nodes = [
  { id: "i1", code: "D", name: "Ilha Sintética", level: "ISLAND", parentId: null, active: true },
  { id: "p1", code: "01", name: "Processo Sintético", level: "PROCESS", parentId: "i1", active: true },
  { id: "a1", code: "01.A", name: "Área Sintética", level: "AREA", parentId: "p1", active: true },
];

function setup() {
  const get = vi.fn().mockResolvedValue({ items: nodes });
  const post = vi.fn().mockResolvedValue({});
  const patch = vi.fn().mockResolvedValue({});
  vi.stubGlobal("useApi", () => ({ get, post, patch }));
  return { wrapper: mount(EapTreeAdmin), get, post, patch };
}

async function settle(wrapper: ReturnType<typeof mount>) {
  for (let i = 0; i < 3; i += 1) {
    await new Promise((resolve) => setTimeout(resolve));
    await wrapper.vm.$nextTick();
  }
}

afterEach(() => vi.unstubAllGlobals());

describe("EapTreeAdmin", () => {
  it("carrega e exibe a hierarquia global Ilha → Processo → Área", async () => {
    const { wrapper, get } = setup();
    await settle(wrapper);

    expect(get).toHaveBeenCalledWith("/eap-nodes");
    const rows = wrapper.findAll("[role='treeitem']");
    expect(rows.map((row) => row.text())).toEqual([
      expect.stringContaining("D"),
      expect.stringContaining("01"),
      expect.stringContaining("01.A"),
    ]);
    expect(rows.map((row) => row.attributes("aria-level"))).toEqual(["1", "2", "3"]);
  });

  it("cria uma Área informando explicitamente o PROCESS pai", async () => {
    const { wrapper, post } = setup();
    await settle(wrapper);

    await wrapper.get("[data-testid='eap-new']").trigger("click");
    await wrapper.get("[data-testid='eap-level']").setValue("AREA");
    await wrapper.get("[data-testid='eap-code']").setValue("01.b");
    await wrapper.get("[data-testid='eap-name']").setValue("Área Sintética B");
    await wrapper.get("[data-testid='eap-parent']").setValue("p1");
    await wrapper.get("[data-testid='eap-form']").trigger("submit");
    await settle(wrapper);

    expect(post).toHaveBeenCalledWith("/eap-nodes", {
      code: "01.B",
      name: "Área Sintética B",
      level: "AREA",
      parentId: "p1",
    });
  });

  it("edita nome e situação sem alterar código, nível ou pai", async () => {
    const { wrapper, patch } = setup();
    await settle(wrapper);

    await wrapper.get("[data-testid='eap-edit-a1']").trigger("click");
    expect((wrapper.get("[data-testid='eap-code']").element as HTMLInputElement).disabled).toBe(true);
    await wrapper.get("[data-testid='eap-name']").setValue("Área revisada");
    await wrapper.get("[data-testid='eap-active']").setValue(false);
    await wrapper.get("[data-testid='eap-form']").trigger("submit");
    await settle(wrapper);

    expect(patch).toHaveBeenCalledWith("/eap-nodes/a1", {
      name: "Área revisada",
      active: false,
    });
  });
});
