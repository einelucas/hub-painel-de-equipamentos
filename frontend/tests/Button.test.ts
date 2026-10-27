import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import Button from "~/components/ui/Button.vue";

describe("Button Element Plus semantics", () => {
  it.each([
    ["default", "el-button--primary"],
    ["success", "el-button--success"],
    ["destructive", "el-button--danger"],
  ] as const)("maps %s to native %s", (variant, nativeClass) => {
    const wrapper = mount(Button, { props: { variant }, slots: { default: "Ação" } });
    expect(wrapper.classes()).toContain(nativeClass);
    wrapper.unmount();
  });

  it("preserves submit type, labels and disabled while loading changes", async () => {
    const wrapper = mount(Button, { props: { type: "submit", disabled: true, loading: true }, attrs: { "aria-label": "Salvar contrato" } });
    expect(wrapper.attributes("type")).toBe("submit");
    expect(wrapper.attributes("aria-label")).toBe("Salvar contrato");
    expect(wrapper.classes()).toContain("is-loading");
    expect(wrapper.find(".hub-button__spinner").exists()).toBe(false);
    await wrapper.setProps({ loading: false });
    expect(wrapper.attributes("disabled")).toBeDefined();
    await wrapper.trigger("click");
    expect(wrapper.emitted("click")).toBeUndefined();
    wrapper.unmount();
  });
});
