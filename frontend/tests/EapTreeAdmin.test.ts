import { mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import EapTreeAdmin from "~/components/admin/EapTreeAdmin.vue";
import { useConfirm } from "~/composables/useConfirm";

const nodes = [
  { id: "i1", code: "D", name: "Ilha Sintética", level: "ISLAND", parentId: null, active: true },
  { id: "p1", code: "01", name: "Processo Sintético", level: "PROCESS", parentId: "i1", active: true },
  { id: "a1", code: "01.A", name: "Área Sintética", level: "AREA", parentId: "p1", active: true },
];

function setup() {
  const get = vi.fn().mockResolvedValue({ items: nodes });
  const post = vi.fn().mockResolvedValue({});
  const patch = vi.fn().mockResolvedValue({});
  const del = vi.fn().mockResolvedValue(undefined);
  vi.stubGlobal("useApi", () => ({ get, post, patch, delete: del }));
  return { wrapper: mount(EapTreeAdmin), get, post, patch, del };
}

async function settle(wrapper: ReturnType<typeof mount>) {
  for (let i = 0; i < 3; i += 1) {
    await new Promise((resolve) => setTimeout(resolve));
    await wrapper.vm.$nextTick();
  }
}

afterEach(() => {
  useConfirm().cancel();
  vi.unstubAllGlobals();
});

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

  it("busca por código ou nome mantendo os ancestrais do nó encontrado", async () => {
    const { wrapper } = setup();
    await settle(wrapper);

    await wrapper.get("[aria-label='Buscar na Árvore EAP']").setValue("01.a");
    expect(wrapper.findAll("[role='treeitem']").map((row) => row.attributes("data-testid"))).toEqual([
      "eap-node-i1",
      "eap-node-p1",
      "eap-node-a1",
    ]);

    await wrapper.get("[aria-label='Buscar na Árvore EAP']").setValue("processo");
    expect(wrapper.findAll("[role='treeitem']").map((row) => row.attributes("data-testid"))).toEqual([
      "eap-node-i1",
      "eap-node-p1",
    ]);

    await wrapper.get("[aria-label='Buscar na Árvore EAP']").setValue("inexistente");
    expect(wrapper.findAll("[role='treeitem']")).toHaveLength(0);
    expect(wrapper.text()).toContain("Nenhum nó corresponde à busca.");
  });

  it("cria uma Área informando explicitamente o PROCESS pai", async () => {
    const { wrapper, post } = setup();
    await settle(wrapper);

    await wrapper.get("[data-testid='eap-new']").trigger("click");
    expect(wrapper.get(".modal-card h2").text()).toBe("Novo nó da Árvore EAP");
    await wrapper.get("[data-testid='eap-level']").setValue("AREA");
    await wrapper.get("[data-testid='eap-code']").setValue("01.b");
    await wrapper.get("[data-testid='eap-name']").setValue("Área Sintética B");
    await wrapper.get("[data-testid='eap-parent']").setValue("p1");
    await wrapper.get("[data-testid='eap-form']").trigger("submit");
    await settle(wrapper);

    expect(wrapper.find(".modal-card").exists()).toBe(false);
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
    expect(wrapper.get(".modal-card h2").text()).toBe("Editar nó da Árvore EAP");
    expect((wrapper.get("[data-testid='eap-code']").element as HTMLInputElement).disabled).toBe(true);
    await wrapper.get("[data-testid='eap-name']").setValue("Área revisada");
    await wrapper.get("[data-testid='eap-active']").setValue(false);
    await wrapper.get("[data-testid='eap-form']").trigger("submit");
    await settle(wrapper);

    expect(wrapper.find(".modal-card").exists()).toBe(false);
    expect(patch).toHaveBeenCalledWith("/eap-nodes/a1", {
      name: "Área revisada",
      active: false,
    });
  });

  it("exclui um nó após confirmação no diálogo", async () => {
    const { wrapper, del } = setup();
    await settle(wrapper);

    await wrapper.get("[data-testid='eap-delete-a1']").trigger("click");
    await wrapper.vm.$nextTick();
    expect(useConfirm().state.open).toBe(true);
    expect(useConfirm().state.message).toContain("01.A");
    useConfirm().accept();
    await settle(wrapper);

    expect(del).toHaveBeenCalledWith("/eap-nodes/a1");
  });
});
