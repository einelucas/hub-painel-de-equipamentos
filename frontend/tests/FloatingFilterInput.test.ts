import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import FloatingFilterInput from "~/components/ui/FloatingFilterInput.vue";

describe("FloatingFilterInput", () => {
  it("flutua a legenda no foco e mantém o mesmo estado quando preenchido", async () => {
    const wrapper = mount(FloatingFilterInput, {
      props: {
        modelValue: "",
        label: "Busca",
        placeholder: "Código ou razão social",
        testId: "supplier-search",
        "onUpdate:modelValue": (value: string) => wrapper.setProps({ modelValue: value }),
      },
    });
    const input = wrapper.get("[data-testid='supplier-search']");

    expect(wrapper.classes()).not.toContain("is-floating");
    await input.trigger("focus");
    expect(wrapper.classes()).toContain("is-floating");
    expect(input.attributes("placeholder")).toBe("Código ou razão social");

    await input.setValue("ACME");
    await input.trigger("blur");
    expect(wrapper.classes()).toContain("is-filled");
    expect(wrapper.classes()).toContain("is-floating");
  });

  it("limpa o valor pelo mesmo affordance dos selects", async () => {
    const wrapper = mount(FloatingFilterInput, {
      props: {
        modelValue: "ACME",
        label: "Busca",
        "onUpdate:modelValue": (value: string) => wrapper.setProps({ modelValue: value }),
      },
    });

    await wrapper.get(".floating-filter-input__clear").trigger("click");
    expect(wrapper.props("modelValue")).toBe("");
    expect(wrapper.emitted("clear")).toHaveLength(1);
  });
});
