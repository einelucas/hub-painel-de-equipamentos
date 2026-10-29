import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import SupplierCombobox from "~/components/imports/SupplierCombobox.vue";
import type { Supplier } from "~/types/equipment";
import { menuOptions, openMenu, optionLabels } from "./support/searchableSelect";

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
        testId: "supplier-combobox",
        suppliers: [
          supplier("z", "9002", "Zeta Industrial"),
          supplier("a", "1001", "Alfa Engenharia"),
        ],
      },
    });
    const input = wrapper.get("input[role='combobox']");

    await openMenu(wrapper, "supplier-combobox");
    expect(await optionLabels(wrapper, "supplier-combobox")).toEqual([
      "Manter sem fornecedor",
      "1001 · Alfa Engenharia",
      "9002 · Zeta Industrial",
    ]);

    await input.setValue("9002");
    await flushPromises();
    expect(
      menuOptions(wrapper, "supplier-combobox").map((item) => item.find(".v-list-item-title").text()),
    ).toEqual(["9002 · Zeta Industrial"]);

    // Esc limpa o texto do filtro e, num segundo Esc, fecha o menu; clicar
    // no campo reabre com todas as opções.
    await input.trigger("keydown", { key: "Escape" });
    await input.trigger("keydown", { key: "Escape" });
    expect(input.attributes("aria-expanded")).toBe("false");
    await openMenu(wrapper, "supplier-combobox");
    expect(input.attributes("aria-expanded")).toBe("true");
    expect(await optionLabels(wrapper, "supplier-combobox")).toEqual([
      "Manter sem fornecedor",
      "1001 · Alfa Engenharia",
      "9002 · Zeta Industrial",
    ]);
  });
});
