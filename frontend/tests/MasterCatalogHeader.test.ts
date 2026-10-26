import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import MasterCatalogHeader from "~/components/master-catalog/MasterCatalogHeader.vue";

function mountHeader(busy = false) {
  return mount(MasterCatalogHeader, {
    props: {
      equipmentCount: 3,
      activeEquipmentCount: 2,
      areaCount: 2,
      componentCount: 5,
      busy,
    },
  });
}

describe("MasterCatalogHeader", () => {
  it("resume o catálogo e emite as ações principais", async () => {
    const wrapper = mountHeader();
    expect(wrapper.get("h1").text()).toBe("Catálogo Mestre");
    expect(wrapper.text()).toContain("3 equipamentos");
    expect(wrapper.text()).toContain("2 áreas ativas");
    expect(wrapper.text()).toContain("5 componentes");
    expect(wrapper.text()).toContain("2 ativos");

    const buttons = wrapper.findAll("button");
    await buttons.find((button) => button.text().includes("Gerenciar áreas"))!.trigger("click");
    await buttons.find((button) => button.text().includes("Importar seed"))!.trigger("click");
    await buttons.find((button) => button.text().includes("Novo equipamento"))!.trigger("click");

    expect(wrapper.emitted("manageAreas")).toHaveLength(1);
    expect(wrapper.emitted("importSeed")).toHaveLength(1);
    expect(wrapper.emitted("create")).toHaveLength(1);
  });

  it("bloqueia as ações enquanto o catálogo está processando", () => {
    const wrapper = mountHeader(true);
    for (const button of wrapper.findAll("button")) {
      expect(button.attributes("disabled")).toBeDefined();
    }
  });
});
