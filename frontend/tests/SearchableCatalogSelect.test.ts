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

  it("sorted=false mantém a ordem recebida e clearable=false esconde a opção vazia", async () => {
    const wrapper = mount(SearchableSelect, {
      props: { options, modelValue: "", label: "EAP", sorted: false, clearable: false, required: true },
    });

    expect(wrapper.get("input").attributes("required")).toBeDefined();
    await wrapper.get("input").trigger("focus");
    expect(wrapper.findAll("[role='option']").map((item) => item.find("strong").text())).toEqual([
      "B · Beta",
      "A · Alfa",
    ]);
  });

  it("emite change só quando o valor muda e digitar não limpa a seleção", async () => {
    const wrapper = mount(SearchableSelect, {
      props: {
        options,
        modelValue: "a",
        label: "EAP",
        "onUpdate:modelValue": (value: string) => wrapper.setProps({ modelValue: value }),
      },
    });

    await wrapper.get("input").trigger("focus");
    await wrapper.get("input").setValue("bet");
    expect(wrapper.emitted("update:modelValue")).toBeUndefined();

    const pick = async (label: string) => {
      await wrapper.get("input").trigger("focus");
      await wrapper.findAll("[role='option']").find((item) => item.find("strong").text() === label)!.trigger("mousedown");
    };
    await pick("A · Alfa");
    expect(wrapper.emitted("change")).toBeUndefined();
    await pick("B · Beta");
    expect(wrapper.emitted("change")).toEqual([["b"]]);
  });

  it("navega pelas opções com as setas e escolhe com Enter", async () => {
    const wrapper = mount(SearchableSelect, {
      props: { options, modelValue: "", label: "EAP", emptyLabel: "Todas" },
    });
    const input = wrapper.get("input");

    await input.trigger("focus");
    await input.trigger("keydown", { key: "ArrowDown" });
    await input.trigger("keydown", { key: "ArrowDown" });
    expect(wrapper.get(".is-active strong").text()).toBe("A · Alfa");
    await input.trigger("keydown", { key: "Enter" });

    expect(wrapper.emitted("change")).toEqual([["a"]]);
    expect(wrapper.find("[role='listbox']").exists()).toBe(false);
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
