import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import SupplierCombobox from "~/components/imports/SupplierCombobox.vue";
import type { Supplier } from "~/types/equipment";

const supplier = (id: string, corporateCode: string, legalName: string): Supplier => ({
  id,
  corporateCode,
  legalName,
  tradeName: null,
  taxId: null,
  active: true,
  createdAt: "2026-10-01T00:00:00Z",
  updatedAt: "2026-10-01T00:00:00Z",
});

describe("SupplierCombobox", () => {
  it("mantém o menu, ordena A–Z e busca por código ou nome", async () => {
    const wrapper = mount(SupplierCombobox, {
      props: {
        modelValue: "",
        label: "Fornecedor",
        suppliers: [
          supplier("z", "9002", "Zeta Industrial"),
          supplier("a", "1001", "Alfa Engenharia"),
        ],
      },
    });

    await wrapper.get("input").trigger("focus");
    expect(wrapper.findAll("[role='option']").map((item) => item.text())).toEqual([
      "Manter sem fornecedor",
      "Alfa EngenhariaCódigo 1001",
      "Zeta IndustrialCódigo 9002",
    ]);

    await wrapper.get("input").setValue("9002");
    expect(wrapper.findAll("[role='option']").map((item) => item.text())).toEqual([
      "Manter sem fornecedor",
      "Zeta IndustrialCódigo 9002",
    ]);

    await wrapper.get("[aria-label='Abrir Fornecedor']").trigger("click");
    expect(wrapper.find("[role='listbox']").exists()).toBe(false);
    await wrapper.get("[aria-label='Abrir Fornecedor']").trigger("click");
    expect(wrapper.find("[role='listbox']").exists()).toBe(true);
  });
});
