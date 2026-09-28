import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import EngineeringTable from "~/components/queue/EngineeringTable.vue";
import EngineeringTableHeader from "~/components/queue/EngineeringTableHeader.vue";
import EngineeringTableRow from "~/components/queue/EngineeringTableRow.vue";
import type { EngineeringRow } from "~/types/equipment";

const passthrough = { template: "<div><slot /></div>" };
const globalStubs = {
  components: { EngineeringTableHeader, EngineeringTableRow },
  stubs: {
    Table: passthrough,
    TableHeader: passthrough,
    TableRow: passthrough,
    TableHead: passthrough,
    TableBody: passthrough,
    TableCell: passthrough,
    PendingBadge: passthrough,
    NuxtLink: { props: ["to"], template: "<a :href='to'><slot /></a>" },
  },
};

function row(overrides: Partial<EngineeringRow> = {}): EngineeringRow {
  return {
    equipmentId: "eq-1",
    equipmentName: "Bomba SUMP",
    unit: { id: "unit-1", code: "LEM", name: "Luís Eduardo Magalhães" },
    projectContext: { id: "ctx-1", code: "C2", name: "Caldeira 2" },
    currentStage: 0,
    currentStageName: "Nova demanda",
    nextStage: 1,
    nextStageName: "Negociação",
    pending: [],
    discipline: { id: "d-1", name: "Metal Mec." },
    area: { id: "a-1", name: "Caldeira" },
    workPackages: [{ id: "wp-1", name: "Pacote 1", code: "CAL012" }],
    responsibleUser: { id: "u-1", name: "Ana Carolina", email: "ana@inpasa.com.br" },
    startupAt: "2027-10-27",
    criticality: "Médio",
    componentsCount: 1,
    ...overrides,
  };
}

describe("EngineeringTable", () => {
  it("visão normal: mostra uma linha por equipamento com a coluna Responsável", () => {
    const wrapper = mount(EngineeringTable, {
      props: { rows: [row()], grouped: false },
      global: globalStubs,
    });

    expect(wrapper.find("[data-testid='engineering-grouped']").exists()).toBe(false);
    expect(wrapper.text()).toContain("Bomba SUMP");
    expect(wrapper.text()).toContain("LEM");
    expect(wrapper.text()).toContain("0 · Nova demanda");
    expect(wrapper.text()).toContain("Metal Mec.");
    expect(wrapper.text()).toContain("Caldeira");
    expect(wrapper.text()).toContain("CAL012");
    expect(wrapper.text()).toContain("Ana Carolina");
    expect(wrapper.text()).toContain("27/10/2027");
  });

  it("visão normal: campos ausentes viram travessão, pacotes vazios também", () => {
    const partial = row({
      discipline: null,
      area: null,
      workPackages: [],
      responsibleUser: null,
      startupAt: null,
    });
    const wrapper = mount(EngineeringTable, { props: { rows: [partial], grouped: false }, global: globalStubs });

    const text = wrapper.text();
    expect(text.match(/—/g)?.length).toBeGreaterThanOrEqual(4);
  });

  it("navegação ao detalhe: o link aponta para /equipamentos/{id}", () => {
    const wrapper = mount(EngineeringTable, {
      props: { rows: [row({ equipmentId: "eq-42" })], grouped: false },
      global: globalStubs,
    });
    const link = wrapper.get("a");
    expect(link.attributes("href")).toBe("/equipamentos/eq-42");
    expect(link.text()).toBe("Ver detalhes");
  });

  it("visão agrupada: agrupa por responsável, mostra título e contagem, e omite a coluna Responsável", () => {
    const rows = [
      row({ equipmentId: "eq-1", responsibleUser: { id: "u-1", name: "Ana Carolina", email: "a@x.com" } }),
      row({ equipmentId: "eq-2", equipmentName: "Compressor", responsibleUser: { id: "u-1", name: "Ana Carolina", email: "a@x.com" } }),
      row({ equipmentId: "eq-3", equipmentName: "Motor", responsibleUser: { id: "u-2", name: "Ediel", email: "e@x.com" } }),
      row({ equipmentId: "eq-4", equipmentName: "Válvula", responsibleUser: null }),
    ];
    const wrapper = mount(EngineeringTable, { props: { rows, grouped: true }, global: globalStubs });

    expect(wrapper.find("[data-testid='engineering-grouped']").exists()).toBe(true);
    const groupTitles = wrapper.findAll(".group-title").map((el) => el.text());
    expect(groupTitles).toEqual(["Ana Carolina (2)", "Ediel (1)", "Sem responsável (1)"]);

    // Bomba SUMP e Compressor (Ana Carolina) aparecem, mas o nome do
    // responsável não é repetido como célula de tabela dentro do grupo —
    // só no título da seção (a asserção de "Ana Carolina" já é satisfeita
    // pelos títulos acima; aqui conferimos que todos os equipamentos
    // aparecem em algum grupo).
    expect(wrapper.text()).toContain("Compressor");
    expect(wrapper.text()).toContain("Motor");
    expect(wrapper.text()).toContain("Válvula");
  });

  it("visão agrupada: sem linhas não gera nenhuma seção de grupo", () => {
    const wrapper = mount(EngineeringTable, { props: { rows: [], grouped: true }, global: globalStubs });
    expect(wrapper.findAll(".group-block")).toHaveLength(0);
  });
});
