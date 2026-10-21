import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import CurrencyInput from "~/components/ui/CurrencyInput.vue";
import {
  editableCurrencyInput,
  formatCurrencyInput,
  parseCurrencyInput,
} from "~/utils/currency";

describe("currency", () => {
  it("interpreta o decimal da API e o formato brasileiro", () => {
    expect(parseCurrencyInput("483600.00")).toBe("483600.00");
    expect(parseCurrencyInput("R$ 1.234,56")).toBe("1234.56");
    expect(parseCurrencyInput("1.234")).toBe("1234.00");
    expect(parseCurrencyInput("2.500,5")).toBe("2500.50");
  });

  it("descarta texto e mantém vazio diferente de zero", () => {
    expect(parseCurrencyInput("")).toBe("");
    expect(parseCurrencyInput("abc")).toBe("");
    expect(parseCurrencyInput("R$ 0,00")).toBe("0.00");
  });

  it("formata para exibição e para edição", () => {
    expect(formatCurrencyInput("483600.00")).toContain("R$");
    expect(formatCurrencyInput("483600.00")).toContain("483.600,00");
    expect(formatCurrencyInput(null)).toBe("");
    expect(editableCurrencyInput("483600.00")).toBe("483600,00");
  });
});

describe("CurrencyInput", () => {
  it("exibe em reais, edita sem separador de milhar e formata ao sair", async () => {
    const wrapper = mount(CurrencyInput, {
      props: { modelValue: "483600.00", label: "Valor" },
    });
    const input = wrapper.get("input");
    expect((input.element as HTMLInputElement).value).toContain("483.600,00");

    await input.trigger("focus");
    expect((input.element as HTMLInputElement).value).toBe("483600,00");

    await input.setValue("1.234,56");
    const emitted = wrapper.emitted("update:modelValue");
    expect(emitted?.[emitted.length - 1]).toEqual(["1234.56"]);

    await input.trigger("blur");
    expect((input.element as HTMLInputElement).value).toContain("1.234,56");
  });

  it("descarta letras digitadas ou coladas", async () => {
    const wrapper = mount(CurrencyInput, {
      props: { modelValue: "", label: "Valor" },
    });
    const input = wrapper.get("input");

    await input.setValue("abc 1.234,56 xyz");
    expect((input.element as HTMLInputElement).value).toBe("1.234,56");
    const emitted = wrapper.emitted("update:modelValue");
    expect(emitted?.[emitted.length - 1]).toEqual(["1234.56"]);
  });
});
