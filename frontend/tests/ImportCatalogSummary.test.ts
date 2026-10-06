import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import ImportCatalogSummary from "~/components/imports/ImportCatalogSummary.vue";
import type { CatalogItem } from "~/types/imports";

// Dados 100% sintéticos.
function item(overrides: Partial<CatalogItem>): CatalogItem {
  return {
    kind: "eap_node",
    key: "77.A",
    action: "EXISTING",
    label: "77.A",
    evidenceSource: null,
    issueCode: null,
    message: null,
    detail: {},
    ...overrides,
  };
}

describe("ImportCatalogSummary", () => {
  it("mostra existente, novo, conflito e pendente por catálogo", () => {
    const wrapper = mount(ImportCatalogSummary, {
      props: {
        catalogs: [
          item({ key: "77.A", action: "EXISTING", label: "77.A" }),
          item({ key: "77.B", action: "CREATE", label: "77.B · Área Sintética", evidenceSource: "OFFICIAL_CATALOG" }),
          item({ key: "77.C", action: "CONFLICT", label: "77.C", message: "Nome diferente no Hub" }),
          item({ kind: "discipline", key: "Disc Sintética", action: "UNRESOLVED", label: "Disc Sintética", message: "Sem sigla" }),
        ],
        responsibles: { resolved: 3, unresolved: 2 },
      },
    });
    const eap = wrapper.get("[data-testid='catalog-eap_node']");
    expect(eap.get("[data-testid='catalog-eap_node-EXISTING']").text()).toContain("Existente: 1");
    expect(eap.get("[data-testid='catalog-eap_node-CREATE']").text()).toContain("Novo — será criado: 1");
    expect(eap.get("[data-testid='catalog-eap_node-CONFLICT']").text()).toContain("Conflito: 1");
    expect(eap.text()).toContain("fonte: catálogo oficial");
    expect(wrapper.get("[data-testid='catalog-discipline-UNRESOLVED']").text()).toContain("Pendente: 1");
    const responsibles = wrapper.get("[data-testid='catalog-responsibles']").text();
    expect(responsibles).toContain("Usuário encontrado: 3");
    expect(responsibles).toContain("importado sem responsável: 2");
  });

  it("não mostra seção de catálogo sem itens", () => {
    const wrapper = mount(ImportCatalogSummary, { props: { catalogs: [] } });
    expect(wrapper.find("[data-testid='catalog-eap_node']").exists()).toBe(false);
  });
});
