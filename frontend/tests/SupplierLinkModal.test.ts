import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import SupplierLinkModal from "~/components/equipment/SupplierLinkModal.vue";
import type { EquipmentSupplier, Supplier } from "~/types/equipment";
import { menuOptions, openMenu } from "./support/searchableSelect";

function supplier(id: string, legalName: string, taxId: string | null = null): Supplier {
  return {
    id,
    corporateCode: null,
    legalName,
    tradeName: null,
    taxId,
    active: true,
    createdAt: "2026-09-20T00:00:00",
    updatedAt: "2026-09-20T00:00:00",
  };
}

const current: EquipmentSupplier = {
  id: "link-1",
  supplier: supplier("s-1", "Principal SA", "12345678000190"),
  role: "Fabricante",
  isPrimary: true,
  startStage: 1,
  endStage: null,
  startedAt: "2026-09-20T00:00:00",
  endedAt: null,
  changeReason: null,
  source: "MANUAL",
  changedByUserId: "user-1",
  createdAt: "2026-09-20T00:00:00",
};

function mountModal(link: EquipmentSupplier | null) {
  return mount(SupplierLinkModal, {
    props: {
      open: true,
      current: link,
      suppliers: [supplier("s-2", "Secundária SA", "98765432000110")],
      busy: false,
      error: "",
    },
    global: {
      stubs: {
        AppModal: { props: ["open", "title"], template: "<div v-if='open'><h2>{{ title }}</h2><slot /></div>" },
        NuxtLink: { props: ["to"], template: "<a :href='to'><slot /></a>" },
      },
    },
  });
}

async function choose(wrapper: ReturnType<typeof mountModal>, label: string) {
  await openMenu(wrapper, "supplier-link-combobox");
  const option = menuOptions(wrapper, "supplier-link-combobox").find((item) =>
    item.text().includes(label),
  );
  if (!option) throw new Error(`Opção '${label}' não encontrada`);
  await option.trigger("click");
}

describe("SupplierLinkModal", () => {
  it("na substituição mostra o que sai e o que entra, com CNPJ formatado", async () => {
    const wrapper = mountModal(current);
    expect(wrapper.get("h2").text()).toBe("Substituir fornecedor");
    expect(wrapper.get("[data-testid='supplier-swap-out']").text()).toContain("12.345.678/0001-90");
    expect(wrapper.get("[data-testid='supplier-swap-in']").text()).toContain("Escolha o fornecedor abaixo");

    await choose(wrapper, "Secundária SA");
    expect(wrapper.get("[data-testid='supplier-swap-in']").text()).toContain("98.765.432/0001-10");
  });

  it("emite o fornecedor escolhido com papel e motivo opcionais", async () => {
    const wrapper = mountModal(current);
    const submit = wrapper.get("button[type='submit']");
    expect(submit.attributes("disabled")).toBeDefined();

    await choose(wrapper, "Secundária SA");
    await wrapper.get("input[maxlength='80']").setValue("  Integrador ");
    await wrapper.get("form").trigger("submit");

    expect(wrapper.emitted("submit")).toEqual([[{ supplierId: "s-2", role: "Integrador", changeReason: null }]]);
  });

  it("no primeiro vínculo mostra só o fornecedor que entra", () => {
    const wrapper = mountModal(null);
    expect(wrapper.get("h2").text()).toBe("Vincular fornecedor");
    expect(wrapper.find("[data-testid='supplier-swap-out']").exists()).toBe(false);
    expect(wrapper.get("button[type='submit']").text()).toBe("Vincular");
  });
});
