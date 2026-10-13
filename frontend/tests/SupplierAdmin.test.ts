import { mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import SupplierAdmin from "~/components/admin/SupplierAdmin.vue";
import AdminPanel from "~/components/admin/AdminPanel.vue";
import type { Supplier } from "~/types/equipment";

function supplier(overrides: Partial<Supplier>): Supplier {
  return {
    id: "s-1",
    corporateCode: "9001",
    legalName: "Fornecedor Sintético SA",
    tradeName: "Sintético",
    taxId: "12345678000190",
    active: true,
    createdAt: "2026-01-01T00:00:00Z",
    updatedAt: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function mountAdmin() {
  const get = vi.fn().mockResolvedValue({
    items: [supplier({}), supplier({ id: "s-2", corporateCode: null, tradeName: null, taxId: null })],
  });
  const patch = vi.fn().mockResolvedValue({});
  const post = vi.fn().mockResolvedValue({});
  vi.stubGlobal("useApi", () => ({ get, patch, post }));
  const wrapper = mount(SupplierAdmin, {
    props: { open: true },
    global: {
      components: { AdminPanel },
      stubs: {
        AppModal: { props: ["open", "title"], template: "<div v-if='open'><slot /></div>" },
        NuxtLink: { props: ["to"], template: "<a :href='to'><slot /></a>" },
      },
    },
  });
  return { wrapper, get, patch, post };
}

async function settle(wrapper: ReturnType<typeof mount>) {
  for (let i = 0; i < 3; i += 1) {
    await new Promise((resolve) => setTimeout(resolve));
    await wrapper.vm.$nextTick();
  }
}

afterEach(() => vi.unstubAllGlobals());

describe("SupplierAdmin", () => {
  it("exibe o CNPJ abaixo do nome no padrão 00.000.000/0000-00", async () => {
    const { wrapper } = mountAdmin();
    await settle(wrapper);

    const row = wrapper.get("[data-testid='supplier-row-s-1']");
    expect(row.get(".cnpj").text()).toBe("12.345.678/0001-90");
    expect(row.text()).toContain("Sintético · 12.345.678/0001-90");
    expect(wrapper.get("[data-testid='supplier-row-s-2']").text()).toContain("sem CNPJ");
  });

  it("edita com o CNPJ mascarado e grava apenas os dígitos", async () => {
    const { wrapper, patch } = mountAdmin();
    await settle(wrapper);

    const edit = wrapper
      .get("[data-testid='supplier-row-s-1']")
      .findAll("button")
      .find((button) => button.text().includes("Editar"));
    await edit!.trigger("click");

    const cnpj = wrapper.get("input[maxlength='18']");
    expect((cnpj.element as HTMLInputElement).value).toBe("12.345.678/0001-90");
    await cnpj.setValue("98765432000110");
    await cnpj.trigger("blur");
    expect((cnpj.element as HTMLInputElement).value).toBe("98.765.432/0001-10");

    await wrapper.get("form").trigger("submit");
    await settle(wrapper);
    expect(patch).toHaveBeenCalledWith("/suppliers/s-1", expect.objectContaining({ taxId: "98765432000110" }));
  });

  it("renderiza apenas o primeiro lote e mostra o total", async () => {
    const items = Array.from({ length: 120 }, (_, n) => supplier({ id: `b-${n}`, legalName: `Fornecedor ${n}` }));
    const get = vi.fn().mockResolvedValue({ items });
    vi.stubGlobal("useApi", () => ({ get, patch: vi.fn(), post: vi.fn() }));
    const wrapper = mount(SupplierAdmin, {
      props: { open: true },
      global: {
        components: { AdminPanel },
        stubs: {
          AppModal: { props: ["open", "title"], template: "<div v-if='open'><slot /></div>" },
          NuxtLink: { props: ["to"], template: "<a :href='to'><slot /></a>" },
        },
      },
    });
    await settle(wrapper);

    expect(wrapper.findAll("[data-testid^='supplier-row-']")).toHaveLength(50);
    expect(wrapper.get("[data-testid='supplier-shown']").text()).toBe("Exibindo 50 de 120");
    expect(wrapper.find("[data-testid='supplier-sentinel']").exists()).toBe(true);
  });
});
