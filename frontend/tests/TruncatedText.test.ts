import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import TruncatedText from "~/components/ui/TruncatedText.vue";

describe("TruncatedText", () => {
  it("exibe o texto completo e sem balão quando está dentro do limite", () => {
    const wrapper = mount(TruncatedText, { props: { text: "Bomba principal" } });

    expect(wrapper.get(".truncated-text-label").text()).toBe("Bomba principal");
    expect(wrapper.find("[role='tooltip']").exists()).toBe(false);
    expect(wrapper.get(".truncated-text").attributes("tabindex")).toBeUndefined();
  });

  it("trunca com reticências e mostra o nome completo no balão", () => {
    const name = "Nome muito longo de equipamento";
    const wrapper = mount(TruncatedText, { props: { text: name, max: 10 } });

    expect(wrapper.get(".truncated-text-label").text()).toBe("Nome muito…");
    expect(wrapper.get("[role='tooltip']").text()).toBe(name);
    expect(wrapper.get(".truncated-text").attributes("tabindex")).toBe("0");
  });

  it("usa o limite padrão de 40 caracteres", () => {
    const name = "A".repeat(41);
    const wrapper = mount(TruncatedText, { props: { text: name } });

    expect(wrapper.get(".truncated-text-label").text()).toBe(`${"A".repeat(40)}…`);
    expect(wrapper.get("[role='tooltip']").text()).toBe(name);
  });
});
