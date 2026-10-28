import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import FloatingFilterSelect from "~/components/ui/FloatingFilterSelect.vue";
import { chooseOption, isDisabled, openMenu, optionLabels, shownValue } from "./support/searchableSelect";

const options = [
  { id: "a", label: "A · Alfa" },
  { id: "b", label: "B · Beta" },
];

function mountSelect(props: Record<string, unknown> = {}) {
  return mount(FloatingFilterSelect, {
    props: {
      modelValue: "",
      label: "Responsável",
      options,
      emptyLabel: "Todos",
      testId: "floating-filter",
      ...props,
    },
  });
}

describe("FloatingFilterSelect", () => {
  it("começa com o label dentro do campo, sem label separado acima", () => {
    const wrapper = mountSelect();
    expect(wrapper.get(".floating-filter-select__label").text()).toBe("Responsável");
    expect(wrapper.classes()).not.toContain("is-floating");
    expect(wrapper.classes()).not.toContain("is-filled");
    expect(wrapper.get(".floating-filter-select__outline").element.tagName).toBe("FIELDSET");
    expect(wrapper.get(".floating-filter-select__legend").text()).toBe("Responsável");
  });

  it("eleva o label ao abrir o menu e mantém elevado ao selecionar uma opção", async () => {
    const wrapper = mountSelect({
      "onUpdate:modelValue": (value: string) => wrapper.setProps({ modelValue: value }),
    });
    const input = wrapper.get(".el-select__input");

    await openMenu(wrapper, "floating-filter");
    expect(wrapper.classes()).toContain("is-open");
    expect(wrapper.classes()).toContain("is-floating");
    expect(wrapper.attributes("data-floating")).toBe("true");

    await chooseOption(wrapper, "floating-filter", "B · Beta");
    expect(wrapper.props("modelValue")).toBe("b");
    expect(wrapper.classes()).toContain("is-filled");
    expect(shownValue(wrapper, "floating-filter")).toBe("B · Beta");

    await input.trigger("blur");
    // Sem foco, mas com valor, o label continua encaixado na borda.
    expect(wrapper.classes()).toContain("is-floating");
  });

  it("volta ao estado inicial quando o valor é limpo e o campo perde o foco", async () => {
    const wrapper = mountSelect({ modelValue: "a" });
    expect(wrapper.classes()).toContain("is-floating");

    await wrapper.setProps({ modelValue: "" });
    expect(wrapper.classes()).not.toContain("is-floating");
    expect(wrapper.attributes("data-floating")).toBe("false");
    expect(shownValue(wrapper, "floating-filter")).toBe("");
  });

  it("mantém opções, limpeza e estado desabilitado integrados ao Element Plus", async () => {
    const wrapper = mountSelect({ disabled: true });
    await flushPromises();
    expect(isDisabled(wrapper, "floating-filter")).toBe(true);
    expect(wrapper.classes()).toContain("is-disabled");
    expect(wrapper.find(".el-select__wrapper").classes()).toContain("is-disabled");

    const enabled = mountSelect();
    expect(await optionLabels(enabled, "floating-filter")).toEqual([
      "Todos",
      "A · Alfa",
      "B · Beta",
    ]);
  });
});
