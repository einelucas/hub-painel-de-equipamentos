import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import SearchableMultiSelect from "~/components/ui/SearchableMultiSelect.vue";
import SearchableSelect from "~/components/ui/SearchableSelect.vue";

const options = [
  { id: "b", label: "B · Beta", description: "Área" },
  { id: "a", label: "A · Alfa", description: "Processo" },
];

describe("seletores pesquisáveis de catálogo", () => {
  it("ordena, busca e seleciona uma opção mantendo o menu", async () => {
    const wrapper = mount(SearchableSelect, {
      props: { options, modelValue: "", label: "EAP", emptyLabel: "Não informada" },
    });

    expect(wrapper.get("input").attributes("placeholder")).toBe("Não informada");
    await wrapper.get("input").trigger("focus");
    expect(wrapper.findAll("[role='option']").map((item) => item.text())).toEqual([
      "Não informada",
      "A · AlfaProcesso",
      "B · BetaÁrea",
    ]);
    await wrapper.get("input").setValue("beta");
    await wrapper.get("[role='option'][aria-selected='false']").trigger("mousedown");
    expect(wrapper.emitted("update:modelValue")?.at(-1)).toEqual(["b"]);
  });

  it("mantém múltiplos valores em chips e permite adicionar/remover", async () => {
    const wrapper = mount(SearchableMultiSelect, {
      props: { options, modelValue: ["a"], label: "Work Packages" },
    });

    expect(wrapper.text()).toContain("A · Alfa");
    await wrapper.get("input").trigger("focus");
    const beta = wrapper.findAll("[role='option']").find((item) => item.text().includes("B · Beta"));
    expect(beta).toBeDefined();
    await beta!.trigger("mousedown");
    expect(wrapper.emitted("update:modelValue")?.at(-1)).toEqual([["a", "b"]]);

    await wrapper.get("[aria-label='Remover A · Alfa']").trigger("click");
    expect(wrapper.emitted("update:modelValue")?.at(-1)).toEqual([[]]);
  });
});
