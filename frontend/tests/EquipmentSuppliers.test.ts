import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import EquipmentSuppliers from "~/components/equipment/EquipmentSuppliers.vue";
import type { EquipmentSupplier } from "~/types/equipment";

function supplier(id: string, legalName: string, isPrimary: boolean): EquipmentSupplier {
  return {
    supplier: {
      id,
      legalName,
      tradeName: null,
      taxId: null,
      active: true,
      createdAt: "2026-09-20T00:00:00",
      updatedAt: "2026-09-20T00:00:00",
    },
    role: isPrimary ? "Fabricante" : null,
    isPrimary,
    createdAt: "2026-09-20T00:00:00",
  };
}

const passthrough = { template: "<div><slot /></div>" };

function mountWith(items: EquipmentSupplier[], can: (permission: string) => boolean) {
  const catalog = items.map((item) => item.supplier).concat({
    id: "s-2",
    legalName: "Secundária SA",
    tradeName: null,
    taxId: null,
    active: true,
    createdAt: "2026-09-20T00:00:00",
    updatedAt: "2026-09-20T00:00:00",
  });
  const get = vi.fn((path: string) =>
    Promise.resolve(path === "/suppliers" ? { items: catalog } : { items }),
  );
  const patch = vi.fn().mockResolvedValue({});
  const put = vi.fn().mockResolvedValue({});
  const del = vi.fn().mockResolvedValue({});
  vi.stubGlobal("useApi", () => ({ get, patch, put, post: vi.fn(), delete: del }));
  vi.stubGlobal("useAuthStore", () => ({ can }));
  vi.stubGlobal("onMounted", (fn: () => void) => fn());

  const wrapper = mount(EquipmentSuppliers, {
    props: { equipmentId: "eq-1" },
    global: {
      stubs: {
        Table: passthrough,
        TableHeader: passthrough,
        TableRow: passthrough,
        TableHead: passthrough,
        TableBody: passthrough,
        TableCell: passthrough,
        AppModal: passthrough,
        NuxtLink: { props: ["to"], template: "<a :href='to'><slot /></a>" },
      },
    },
  });
  return { wrapper, get, patch, put, del };
}

describe("EquipmentSuppliers", () => {
  it("lista o único fornecedor vinculado (Etapa 7A: no máximo um por equipamento)", async () => {
    const { wrapper } = mountWith([supplier("s-1", "Principal SA", true)], () => true);
    await new Promise((resolve) => setTimeout(resolve));
    await wrapper.vm.$nextTick();

    expect(wrapper.text()).toContain("Principal SA");
    expect(wrapper.get("[data-testid='supplier-s-1']").text()).toContain("Principal SA");
    expect(wrapper.find("[data-testid='replace-supplier']").exists()).toBe(true);
  });

  it("permite substituir o fornecedor vinculado (PUT, não outro POST)", async () => {
    const { wrapper, put } = mountWith([supplier("s-1", "Principal SA", true)], () => true);
    await new Promise((resolve) => setTimeout(resolve));
    await wrapper.vm.$nextTick();

    await wrapper.get("[data-testid='replace-supplier']").trigger("click");
    await new Promise((resolve) => setTimeout(resolve));
    await wrapper.vm.$nextTick();
    await wrapper.get("select").setValue("s-2");
    await wrapper.get("form").trigger("submit");

    expect(put).toHaveBeenCalledWith("/equipments/eq-1/suppliers", {
      supplierId: "s-2",
      role: null,
      isPrimary: true,
    });
  });

  it("esconde as ações de escrita de quem não tem suppliers:write", async () => {
    const { wrapper } = mountWith(
      [supplier("s-1", "Principal SA", true)],
      (permission) => permission !== "suppliers:write",
    );
    await new Promise((resolve) => setTimeout(resolve));
    await wrapper.vm.$nextTick();

    expect(wrapper.text()).not.toContain("Vincular fornecedor");
    expect(wrapper.text()).not.toContain("Desvincular");
  });

  it("mostra estado vazio sem bloquear o processo", async () => {
    const { wrapper } = mountWith([], () => true);
    await new Promise((resolve) => setTimeout(resolve));
    await wrapper.vm.$nextTick();

    expect(wrapper.get("[data-testid='suppliers-empty']").text()).toContain(
      "Nenhum fornecedor vinculado",
    );
  });
});
