import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import SearchableMultiSelect from "~/components/ui/SearchableMultiSelect.vue";
import SearchableSelect from "~/components/ui/SearchableSelect.vue";
import {
  menuOptions,
  openMenu,
  optionLabels,
} from "./support/searchableSelect";

const options = [
  { id: "b", label: "B · Beta", description: "Área" },
  { id: "a", label: "A · Alfa", description: "Processo" },
];

describe("seletores pesquisáveis de catálogo", () => {
  it("ordena, busca e seleciona uma opção mantendo o menu", async () => {
    const wrapper = mount(SearchableSelect, {
      props: {
        options,
        modelValue: "",
        label: "EAP",
        emptyLabel: "Não informada",
        testId: "catalog-select",
      },
    });

    expect(wrapper.get(".el-select__placeholder").text()).toBe("Não informada");
    const input = wrapper.get(".el-select__input");
    await input.trigger("click");
    expect(await optionLabels(wrapper, "catalog-select")).toEqual([
      "Não informada",
      "A · Alfa",
      "B · Beta",
    ]);
    await input.setValue("beta");
    const visible = menuOptions(wrapper, "catalog-select");
    expect(visible.map((item) => item.find("strong").text())).toEqual([
      "Não informada",
      "B · Beta",
    ]);
    await visible
      .find((item) => item.find("strong").text() === "B · Beta")!
      .trigger("click");
    expect(wrapper.emitted("update:modelValue")?.at(-1)).toEqual(["b"]);
  });

  it("does not block native form validation when a required select is disabled", async () => {
    const wrapper = mount(SearchableSelect, { props: { options: [], modelValue: "", label: "Obra", required: true, disabled: true } });
    await flushPromises();
    const input = wrapper.get(".searchable-select__required").element as HTMLInputElement;
    expect(input.checkValidity()).toBe(true);
    await wrapper.setProps({ disabled: false });
    expect(input.checkValidity()).toBe(false);
    wrapper.unmount();
  });

  it("sorted=false mantém a ordem recebida e clearable=false esconde a opção vazia", async () => {
    const wrapper = mount(SearchableSelect, {
      props: {
        options,
        modelValue: "",
        label: "EAP",
        sorted: false,
        clearable: false,
        required: true,
        testId: "catalog-select",
      },
    });

    expect(wrapper.get(".searchable-select__required").attributes("required")).toBeDefined();
    await openMenu(wrapper, "catalog-select");
    expect(await optionLabels(wrapper, "catalog-select")).toEqual([
      "B · Beta",
      "A · Alfa",
    ]);
  });

  it("emite change só quando o valor muda e digitar não limpa a seleção", async () => {
    const wrapper = mount(SearchableSelect, {
      props: {
        options,
        modelValue: "a",
        label: "EAP",
        testId: "catalog-select",
        "onUpdate:modelValue": (value: string) => wrapper.setProps({ modelValue: value }),
      },
    });
    const input = wrapper.get(".el-select__input");

    await input.trigger("click");
    await input.setValue("bet");
    expect(wrapper.emitted("update:modelValue")).toBeUndefined();

    // Esc limpa o texto do filtro e, num segundo Esc, fecha o menu; ao reabrir,
    // o ElSelect reaplica o filtro com texto vazio e todas as opções voltam.
    await input.trigger("keydown", { key: "Escape" });
    await input.trigger("keydown", { key: "Escape" });
    await openMenu(wrapper, "catalog-select");
    await menuOptions(wrapper, "catalog-select")
      .find((item) => item.find("strong").text() === "A · Alfa")!
      .trigger("click");
    expect(wrapper.emitted("change")).toBeUndefined();

    await openMenu(wrapper, "catalog-select");
    await menuOptions(wrapper, "catalog-select")
      .find((item) => item.find("strong").text() === "B · Beta")!
      .trigger("click");
    expect(wrapper.emitted("change")).toEqual([["b"]]);
  });

  it("navega pelas opções com as setas e escolhe com Enter", async () => {
    const wrapper = mount(SearchableSelect, {
      props: { options, modelValue: "", label: "EAP", emptyLabel: "Todas", testId: "catalog-select" },
    });
    const input = wrapper.get(".el-select__input");

    await input.trigger("click");
    await input.trigger("keydown", { key: "ArrowDown" });
    const hovering = menuOptions(wrapper, "catalog-select").find((item) =>
      item.classes().includes("is-hovering"),
    );
    expect(hovering?.find("strong").text()).toBe("A · Alfa");
    await input.trigger("keydown", { key: "Enter" });

    expect(wrapper.emitted("change")).toEqual([["a"]]);
    // O menu fecha semanticamente; a transição de saída pode manter o nó no DOM.
    expect(input.attributes("aria-expanded")).toBe("false");
  });

  it("mantém múltiplos valores em chips e permite adicionar/remover", async () => {
    const wrapper = mount(SearchableMultiSelect, {
      props: { options, modelValue: ["a"], label: "Work Packages", testId: "catalog-multi" },
    });

    await flushPromises();
    expect(wrapper.text()).toContain("A · Alfa");
    await openMenu(wrapper, "catalog-multi");
    const beta = menuOptions(wrapper, "catalog-multi").find((item) =>
      item.text().includes("B · Beta"),
    );
    expect(beta).toBeDefined();
    await beta!.trigger("click");
    expect(wrapper.emitted("update:modelValue")?.at(-1)).toEqual([["a", "b"]]);

    await wrapper.get(".el-tag__close").trigger("click");
    expect(wrapper.emitted("update:modelValue")?.at(-1)).toEqual([[]]);
  });
});
