import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import BackLink from "~/components/ui/BackLink.vue";

const NuxtLink = {
  props: ["to"],
  template: '<a :href="to"><slot /></a>',
};

const global = { stubs: { NuxtLink } };

describe("BackLink", () => {
  it("renderiza link de navegação com ícone e rótulo", () => {
    const wrapper = mount(BackLink, {
      global,
      props: { to: "/dashboard" },
      slots: { default: "Voltar ao painel" },
    });

    expect(wrapper.element.tagName).toBe("A");
    expect(wrapper.attributes("href")).toBe("/dashboard");
    expect(wrapper.text()).toContain("Voltar ao painel");
    expect(wrapper.find("svg").exists()).toBe(true);
    expect(wrapper.get(".back-link__icon").attributes("aria-hidden")).toBe("true");
  });

  it("usa botão e emite clique quando não recebe destino", async () => {
    const wrapper = mount(BackLink, {
      global,
      slots: { default: "Voltar" },
    });

    expect(wrapper.element.tagName).toBe("BUTTON");
    expect(wrapper.attributes("type")).toBe("button");
    await wrapper.trigger("click");
    expect(wrapper.emitted("click")).toHaveLength(1);
  });

  it("aplica a variante compacta do cabeçalho", () => {
    const wrapper = mount(BackLink, {
      global,
      props: { compact: true },
    });

    expect(wrapper.classes()).toContain("v-btn--size-x-small");
  });
});
