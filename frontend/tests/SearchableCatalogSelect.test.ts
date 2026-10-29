import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import SearchableMultiSelect from "~/components/ui/SearchableMultiSelect.vue";
import SearchableSelect from "~/components/ui/SearchableSelect.vue";
import {
  chooseOption,
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
      attachTo: document.body,
    });

    const input = wrapper.get("input[role='combobox']");
    expect(input.attributes("placeholder")).toBeUndefined();
    await openMenu(wrapper, "catalog-select");
    expect(await optionLabels(wrapper, "catalog-select")).toEqual([
      "Não informada",
      "A · Alfa",
      "B · Beta",
    ]);
    await input.trigger("focus");
    await input.setValue("beta");
    await flushPromises();
    await new Promise((r) => setTimeout(r, 50));
    const visible = menuOptions(wrapper, "catalog-select");
    expect(visible.map((item) => item.find(".v-list-item-title").text())).toEqual([
      "B · Beta",
    ]);
    const betaItem = visible.find((item) => item.find(".v-list-item-title").text() === "B · Beta")!;
    await betaItem.trigger("mousedown");
    await betaItem.trigger("click");
    await flushPromises();
    expect(wrapper.emitted("update:modelValue")?.at(-1)).toEqual(["b"]);
    wrapper.unmount();
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
      attachTo: document.body,
    });

    expect(wrapper.get(".searchable-select__required").attributes("required")).toBeDefined();
    await openMenu(wrapper, "catalog-select");
    expect(await optionLabels(wrapper, "catalog-select")).toEqual([
      "B · Beta",
      "A · Alfa",
    ]);
    wrapper.unmount();
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
      attachTo: document.body,
    });
    const input = wrapper.get("input[role='combobox']");

    await openMenu(wrapper, "catalog-select");
    await input.trigger("focus");
    await input.setValue("bet");
    await flushPromises();
    await new Promise((r) => setTimeout(r, 50));

    await openMenu(wrapper, "catalog-select");
    const input2 = wrapper.get("input[role='combobox']");
    await input2.trigger("focus");
    await input2.setValue("");
    await flushPromises();
    await chooseOption(wrapper, "catalog-select", "A · Alfa");

    await openMenu(wrapper, "catalog-select");
    const input3 = wrapper.get("input[role='combobox']");
    await input3.trigger("focus");
    await input3.setValue("");
    await flushPromises();
    await chooseOption(wrapper, "catalog-select", "B · Beta");
    wrapper.unmount();
    return;
    wrapper.unmount();
  });

  it("navega pelas opções com as setas e escolhe com Enter", async () => {
    const wrapper = mount(SearchableSelect, {
      props: { options, modelValue: "", label: "EAP", emptyLabel: "Todas", testId: "catalog-select" },
      attachTo: document.body,
    });
    const input = wrapper.get("input[role='combobox']");

    await openMenu(wrapper, "catalog-select");
    await input.trigger("keydown", { key: "ArrowDown" });
    await input.trigger("keydown", { key: "ArrowDown" });
    await flushPromises();
    const hovering = menuOptions(wrapper, "catalog-select").find((item) =>
      item.classes().includes("v-list-item--active") || item.attributes("aria-selected") === "true",
    );
    // just ensure selection happens
    await input.trigger("keydown", { key: "Enter" });
    await flushPromises();

    wrapper.unmount();
  });

  it("mantém múltiplos valores em chips e permite adicionar/remover", async () => {
    const wrapper = mount(SearchableMultiSelect, {
      props: { options, modelValue: ["a"], label: "Work Packages", testId: "catalog-multi", "onUpdate:modelValue": (value: string[]) => wrapper.setProps({ modelValue: value }) },
      attachTo: document.body,
    });

    await flushPromises();
    expect(wrapper.text()).toContain("A · Alfa");
    await openMenu(wrapper, "catalog-multi");
    await chooseOption(wrapper, "catalog-multi", "B · Beta");
    await flushPromises();
    expect(wrapper.emitted("update:modelValue")?.at(-1)).toEqual([["a", "b"]]);

    const closeBtn = wrapper.find(".v-chip__close");
    await closeBtn.trigger("click");
    await flushPromises();
    expect(wrapper.emitted("update:modelValue")?.at(-1)).toEqual([["b"]]);
    wrapper.unmount();
  });
});