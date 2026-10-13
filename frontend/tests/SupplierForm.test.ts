import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import SupplierForm from "~/components/supplier/SupplierForm.vue";
import type { Supplier } from "~/types/equipment";

const existing: Supplier = {
  id: "s-1",
  corporateCode: "9001",
  legalName: "Fornecedor Sintético SA",
  tradeName: "Sintético",
  taxId: "11222333000181",
  active: true,
  createdAt: "2026-01-01T00:00:00Z",
  updatedAt: "2026-01-01T00:00:00Z",
};

describe("SupplierForm", () => {
  it("mostra a prévia do rótulo dos seletores enquanto se digita", async () => {
    const wrapper = mount(SupplierForm, { props: { supplier: null, saving: false } });
    expect(wrapper.get("[data-testid='supplier-preview']").text()).toContain("sem CNPJ");

    await wrapper.get("[data-testid='supplier-code']").setValue("9001");
    await wrapper.get("input[maxlength='200'][required]").setValue("Nova Indústria SA");
    expect(wrapper.get("[data-testid='supplier-preview'] strong").text()).toBe("9001 · Nova Indústria SA");
  });

  it("mascara o CNPJ ao digitar e avisa quando os dígitos não conferem", async () => {
    const wrapper = mount(SupplierForm, { props: { supplier: null, saving: false } });
    const cnpj = wrapper.get("input[maxlength='18']");

    await cnpj.setValue("11222333000180");
    expect((cnpj.element as HTMLInputElement).value).toBe("11.222.333/0001-80");
    expect(wrapper.get("[data-testid='cnpj-status']").text()).toBe("Dígitos verificadores não conferem");

    await cnpj.setValue("11222333000181");
    expect(wrapper.get("[data-testid='cnpj-status']").text()).toBe("CNPJ válido");
  });

  it("na edição parte do cadastro e envia só dígitos no CNPJ, com a situação", async () => {
    const wrapper = mount(SupplierForm, { props: { supplier: existing, saving: false } });
    expect((wrapper.get("input[maxlength='18']").element as HTMLInputElement).value).toBe("11.222.333/0001-81");

    await wrapper.get("input[type='checkbox']").setValue(false);
    await wrapper.get("form").trigger("submit");

    expect(wrapper.emitted("submit")).toEqual([
      [
        {
          corporateCode: "9001",
          legalName: "Fornecedor Sintético SA",
          tradeName: "Sintético",
          taxId: "11222333000181",
          active: false,
        },
      ],
    ]);
  });

  it("exige a razão social", async () => {
    const wrapper = mount(SupplierForm, { props: { supplier: null, saving: false } });
    await wrapper.get("form").trigger("submit");
    expect(wrapper.emitted("submit")).toBeUndefined();
    expect(wrapper.get("[role='alert']").text()).toBe("Informe a razão social.");
  });
});
