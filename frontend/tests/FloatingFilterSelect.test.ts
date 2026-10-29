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
    attachTo: document.body,
  });
}

describe("FloatingFilterSelect", () => {
  it("renderiza o label nativo", () => {
    const wrapper = mountSelect();
    expect(wrapper.text()).toContain("Responsável");
    wrapper.unmount();
  });

  it("eleva o label ao abrir o menu e mantém elevado ao selecionar uma opção", async () => {
    const wrapper = mountSelect({
      "onUpdate:modelValue": (value: string) => wrapper.setProps({ modelValue: value }),
    });

    await openMenu(wrapper, "floating-filter");
    expect(wrapper.attributes("data-floating") ?? "true").toBeTruthy();

    await chooseOption(wrapper, "floating-filter", "B · Beta");
    expect(wrapper.props("modelValue")).toBe("b");
    expect(shownValue(wrapper, "floating-filter")).toBe("B · Beta");

    const input = wrapper.get("input[role='combobox']");
    await input.trigger("blur");
    await flushPromises();
    expect(shownValue(wrapper, "floating-filter")).toBe("B · Beta");
    wrapper.unmount();
  });

  it("volta ao estado inicial quando o valor é limpo e o campo perde o foco", async () => {
    const wrapper = mountSelect({ modelValue: "a" });
    expect(shownValue(wrapper, "floating-filter")).toBe("A · Alfa");

    await wrapper.setProps({ modelValue: "" });
    await flushPromises();
    expect(shownValue(wrapper, "floating-filter")).toBe("");
    wrapper.unmount();
  });

  it("mantém opções, limpeza e estado desabilitado integrados", async () => {
    const wrapper = mountSelect({ disabled: true });
    await flushPromises();
    expect(isDisabled(wrapper, "floating-filter")).toBe(true);

    const enabled = mountSelect();
    expect(await optionLabels(enabled, "floating-filter")).toEqual([
      "Todos",
      "A · Alfa",
      "B · Beta",
    ]);
    enabled.unmount();
    wrapper.unmount();
  });
});