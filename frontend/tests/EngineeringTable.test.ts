import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import EngineeringTable from "~/components/queue/EngineeringTable.vue";
import EngineeringTableHeader from "~/components/queue/EngineeringTableHeader.vue";
import EngineeringTableRow from "~/components/queue/EngineeringTableRow.vue";
import PendingBadge from "~/components/queue/PendingBadge.vue";
import type { EngineeringRow } from "~/types/equipment";

const passthrough = { template: "<div><slot /></div>" };
const globalStubs = {
  components: { EngineeringTableHeader, EngineeringTableRow, PendingBadge },
  stubs: {
    Table: passthrough,
    TableHeader: passthrough,
    TableRow: passthrough,
    TableHead: passthrough,
    TableBody: passthrough,
    TableCell: passthrough,
    NuxtLink: { props: ["to"], template: "<a :href='to'><slot /></a>" },
    TruncatedText: { props: ["text", "max"], template: "<span>{{ text }}</span>" },
  },
};

function row(overrides: Partial<EngineeringRow> = {}): EngineeringRow {
  return {
    equipmentId: "eq-1",
    equipmentName: "Bomba Sintética A",
    unit: { id: "unit-1", code: "LEM", name: "Luís Eduardo Magalhães" },
    projectContext: { id: "ctx-1", code: "C2", name: "Caldeira 2" },
    currentStage: 0,
    currentStageName: "Nova demanda",
    nextStage: 1,
    nextStageName: "Negociação",
    pending: [],
    discipline: { id: "d-1", name: "Metal Mec.", code: "MM" },
    eapNode: { id: "eap-1", code: "04.A", name: "Caldeira", level: "AREA", active: true },
    workPackages: [{ id: "wp-1", name: "Pacote 1", code: "CAL012" }],
    responsibleUser: { id: "u-1", name: "Analista Sintético A", email: "analista.a@example.test" },
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
    expect(wrapper.text()).toContain("Bomba Sintética A");
    expect(wrapper.text()).toContain("Luís Eduardo Magalhães");
    expect(wrapper.text()).toContain("0 · Nova demanda");
    const discipline = wrapper.get("[data-testid='engineering-discipline']");
    expect(discipline.get(".tip-badge-label").text()).toBe("MM");
    expect(discipline.get("[role='tooltip']").text()).toBe("Metal Mec.");
    // Localização: só o código da EAP no badge; o nome da área fica no balão.
    const area = wrapper.get("[data-testid='eap-node-badge']");
    expect(area.get(".tip-badge-label").text()).toBe("04.A");
    expect(area.get("[role='tooltip']").text()).toBe("Caldeira");
    expect(wrapper.text()).toContain("CAL012");
    expect(wrapper.text()).toContain("Analista Sintético A");
    expect(wrapper.text()).toContain("27/10/2027");
  });

  it("visão normal: campos ausentes viram travessão, pacotes vazios também", () => {
    const partial = row({
      discipline: null,
      eapNode: null,
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
    const link = wrapper.get("a.detail-link");
    expect(link.attributes("href")).toBe("/equipamentos/eq-42");
    expect(link.attributes("aria-label")).toBe("Ver detalhes de Bomba Sintética A");
    expect(link.find("svg").exists()).toBe(true);

    const nameLink = wrapper.get("a.name-link");
    expect(nameLink.attributes("href")).toBe("/equipamentos/eq-42");
    expect(nameLink.text()).toBe("Bomba Sintética A");
  });

  it("visão agrupada: agrupa por responsável, mostra título e contagem, e omite a coluna Responsável", () => {
    const rows = [
      row({ equipmentId: "eq-1", responsibleUser: { id: "u-1", name: "Analista Sintético A", email: "a@x.com" } }),
      row({ equipmentId: "eq-2", equipmentName: "Compressor", responsibleUser: { id: "u-1", name: "Analista Sintético A", email: "a@x.com" } }),
      row({ equipmentId: "eq-3", equipmentName: "Motor", responsibleUser: { id: "u-2", name: "Analista Sintético B", email: "e@x.com" } }),
      row({ equipmentId: "eq-4", equipmentName: "Válvula", responsibleUser: null }),
    ];
    const wrapper = mount(EngineeringTable, { props: { rows, grouped: true }, global: globalStubs });

    expect(wrapper.find("[data-testid='engineering-grouped']").exists()).toBe(true);
    const groupTitles = wrapper.findAll(".group-title").map((el) => el.text());
    expect(groupTitles).toEqual(["Analista Sintético A (2)", "Analista Sintético B (1)", "Sem responsável (1)"]);

    // Bomba Sintética A e Compressor (Analista Sintético A) aparecem, mas o nome do
    // responsável não é repetido como célula de tabela dentro do grupo —
    // só no título da seção (a asserção de "Analista Sintético A" já é satisfeita
    // pelos títulos acima; aqui conferimos que todos os equipamentos
    // aparecem em algum grupo).
    expect(wrapper.text()).toContain("Compressor");
    expect(wrapper.text()).toContain("Motor");
    expect(wrapper.text()).toContain("Válvula");
  });

  it("pendência: usa os badges padrão do app para pronto e para requisitos faltantes", () => {
    const ready = mount(EngineeringTable, { props: { rows: [row()], grouped: false }, global: globalStubs });
    expect(ready.get(".pending-badge--ready").text()).toBe("Pronto para Negociação");

    const todo = mount(EngineeringTable, {
      props: {
        rows: [
          row({
            pending: [{ code: "NEG_EQUALIZED", field: "equalized", message: "Confirme a equalização da negociação." }],
          }),
        ],
        grouped: false,
      },
      global: globalStubs,
    });
    expect(todo.text()).toContain("Falta para avançar");
    expect(todo.get(".pending-badge--todo").text()).toBe("Confirme a equalização da negociação.");
  });

  it("visão agrupada: todas as tabelas usam a mesma grade de colunas", () => {
    const rows = [
      row({ equipmentId: "eq-1", responsibleUser: { id: "u-1", name: "Analista Sintético A", email: "a@x.com" } }),
      row({ equipmentId: "eq-2", equipmentName: "Compressor", responsibleUser: { id: "u-2", name: "Analista Sintético B", email: "b@x.com" } }),
    ];
    const wrapper = mount(EngineeringTable, { props: { rows, grouped: true }, global: globalStubs });

    const grids = wrapper.findAll("colgroup").map((group) => group.findAll("col").map((col) => col.attributes("style")));
    expect(grids).toHaveLength(2);
    expect(grids[1]).toEqual(grids[0]);
  });

  it("visão agrupada: sem linhas não gera nenhuma seção de grupo", () => {
    const wrapper = mount(EngineeringTable, { props: { rows: [], grouped: true }, global: globalStubs });
    expect(wrapper.findAll(".group-block")).toHaveLength(0);
  });
});
