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
  const get = vi.fn().mockResolvedValue({ items });
  const patch = vi.fn().mockResolvedValue({});
  const del = vi.fn().mockResolvedValue({});
  vi.stubGlobal("useApi", () => ({ get, patch, post: vi.fn(), delete: del }));
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
  return { wrapper, get, patch, del };
}

describe("EquipmentSuppliers", () => {
  it("lista os vínculos e destaca o fornecedor principal", async () => {
    const { wrapper } = mountWith(
      [supplier("s-1", "Principal SA", true), supplier("s-2", "Secundária SA", false)],
      () => true,
    );
    await new Promise((resolve) => setTimeout(resolve));
    await wrapper.vm.$nextTick();

    expect(wrapper.text()).toContain("Principal SA");
    expect(wrapper.text()).toContain("Secundária SA");
    const badges = wrapper.findAll("[data-testid='primary-badge']");
    expect(badges).toHaveLength(1);
    expect(wrapper.get("[data-testid='supplier-s-1']").text()).toContain("Principal");
  });

  it("permite promover outro fornecedor a principal", async () => {
    const { wrapper, patch } = mountWith(
      [supplier("s-1", "Principal SA", true), supplier("s-2", "Secundária SA", false)],
      () => true,
    );
    await new Promise((resolve) => setTimeout(resolve));
    await wrapper.vm.$nextTick();

    const promote = wrapper
      .get("[data-testid='supplier-s-2']")
      .findAll("button")
      .find((button) => button.text().includes("Definir como principal"));
    await promote!.trigger("click");

    expect(patch).toHaveBeenCalledWith("/equipments/eq-1/suppliers/s-2", { isPrimary: true });
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
