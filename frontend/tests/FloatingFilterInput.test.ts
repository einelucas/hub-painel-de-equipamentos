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
    const input = wrapper.get("[data-testid='supplier-search'] input");

    expect(wrapper.find(".v-field--focused").exists()).toBe(false);
    await input.trigger("focus");
    expect(wrapper.find(".v-field--focused").exists()).toBe(true);
    expect(input.attributes("placeholder")).toBe("Código ou razão social");

    await input.setValue("ACME");
    await input.trigger("blur");
    expect(wrapper.find(".v-field--dirty").exists()).toBe(true);
    expect(wrapper.find(".v-field-label--floating").text()).toBe("Busca");
  });

  it("limpa o valor pelo mesmo affordance dos selects", async () => {
    const wrapper = mount(FloatingFilterInput, {
      props: {
        modelValue: "ACME",
        label: "Busca",
        "onUpdate:modelValue": (value: string) => wrapper.setProps({ modelValue: value }),
      },
    });

    await wrapper.get(".v-field__clearable [role='button']").trigger("click");
    expect(wrapper.props("modelValue")).toBe("");
    expect(wrapper.emitted("clear")).toHaveLength(1);
  });
});
