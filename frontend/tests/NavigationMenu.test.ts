import { mount } from "@vue/test-utils";
import { defineComponent, markRaw } from "vue";
import { describe, expect, it } from "vitest";
import NavigationMenu from "~/components/ui/NavigationMenu.vue";

const TestIcon = markRaw(defineComponent({ template: "<svg />" }));

describe("NavigationMenu", () => {
  it("renderiza badge, estado ativo e emite a nova seção", async () => {
    const wrapper = mount(NavigationMenu, {
      props: {
        modelValue: "process",
        ariaLabel: "Seções do equipamento",
        items: [
          { value: "process", label: "Processo", icon: TestIcon },
          { value: "components", label: "Componentes", icon: TestIcon, badge: 2 },
        ],
      },
    });

    expect(wrapper.get("nav").attributes("aria-label")).toBe("Seções do equipamento");
    expect(wrapper.findAll("[role='tab']")[0]?.attributes("aria-selected")).toBe("true");
    expect(wrapper.get(".analysis-nav__badge").text()).toBe("2");

    await wrapper.findAll("[role='tab']")[1]!.trigger("click");
    expect(wrapper.emitted("update:modelValue")).toEqual([["components"]]);
  });
});
