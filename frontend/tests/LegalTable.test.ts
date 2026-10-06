import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import LegalTable from "~/components/queue/LegalTable.vue";
import LegalTableHeader from "~/components/queue/LegalTableHeader.vue";
import LegalTableRow from "~/components/queue/LegalTableRow.vue";
import PendingBadge from "~/components/queue/PendingBadge.vue";
import type { LegalRow } from "~/types/equipment";

const passthrough = { template: "<div><slot /></div>" };
const cell = { template: "<div class='cell'><slot /></div>" };
const head = { template: "<div class='head'><slot /></div>" };
const tableRow = { template: "<div class='row'><slot /></div>" };
const globalStubs = {
  components: { LegalTableHeader, LegalTableRow, PendingBadge },
  stubs: {
    Table: passthrough,
    TableHeader: passthrough,
    TableBody: passthrough,
    TableRow: tableRow,
    TableHead: head,
    TableCell: cell,
    NuxtLink: { props: ["to"], template: "<a :href='to'><slot /></a>" },
  },
};

function row(overrides: Partial<LegalRow> = {}): LegalRow {
  return {
    equipmentId: "eq-1",
    equipmentName: "Bomba Sintética A",
    unit: { id: "unit-1", code: "LEM", name: "Luís Eduardo Magalhães" },
    projectContext: { id: "ctx-1", code: "C2", name: "Caldeira 2" },
    currentStage: 4,
    currentStageName: "Aprovação da minuta",
    nextStage: 5,
    nextStageName: "Escrituração do contrato",
    pending: [],
    responsibleUser: { id: "u-1", name: "Analista Sintético A", email: "analista.a@example.test" },
    openedAt: "2027-03-15",
    ticketNumber: "CH-1234",
    draftPrepared: true,
    draftApproved: false,
    contractNumber: "CT-987",
    executedAt: "2027-04-02",
    deliveryAt: "2027-10-27",
    ...overrides,
  };
}

function cellsOf(wrapper: ReturnType<typeof mount>, index = 0): string[] {
  const bodyRows = wrapper.findAll(".row").filter((item) => item.findAll(".cell").length > 0);
  return bodyRows[index]!.findAll(".cell").map((item) => item.text());
}

describe("LegalTable", () => {
  it("renderiza exatamente as colunas atuais da fila jurídica", () => {
    const wrapper = mount(LegalTable, { props: { rows: [row()] }, global: globalStubs });
    expect(wrapper.findAll(".head").map((item) => item.text())).toEqual([
      "Equipamento",
      "Unidade",
      "Responsável",
      "Etapa",
      "Chamado",
      "Abertura",
      "Minuta elaborada",
      "Minuta aprovada",
      "Contrato",
      "Escrituração",
      "Entrega contratual",
      "Pendência",
      "",
    ]);
  });

  it("renderiza um LegalRow com equipamento, unidade, responsável, etapa, chamado, contrato e datas formatadas", () => {
    const wrapper = mount(LegalTable, { props: { rows: [row()] }, global: globalStubs });
    const cells = cellsOf(wrapper);
    expect(cells[0]).toBe("Bomba Sintética A");
    expect(cells[1]).toBe("Luís Eduardo Magalhães");
    expect(cells[2]).toBe("Analista Sintético A");
    expect(cells[3]).toBe("4 · Aprovação da minuta");
    expect(cells[4]).toBe("CH-1234");
    expect(cells[5]).toBe("15/03/2027");
    expect(cells[8]).toBe("CT-987");
    expect(cells[9]).toBe("02/04/2027");
    expect(cells[10]).toBe("27/10/2027");
  });

  it("exibe a etapa com o mesmo selo colorido das outras filas", () => {
    const wrapper = mount(LegalTable, { props: { rows: [row()] }, global: globalStubs });
    const badge = wrapper.get(".stage-badge");
    expect(badge.text()).toBe("4 · Aprovação da minuta");
    expect(badge.classes()).toContain("stage-badge--progress");
  });

  it("converte as flags de minuta em Sim/Não", () => {
    const wrapper = mount(LegalTable, {
      props: { rows: [row({ draftPrepared: true, draftApproved: false }), row({ equipmentId: "eq-2", draftPrepared: false, draftApproved: true })] },
      global: globalStubs,
    });
    expect(cellsOf(wrapper, 0).slice(6, 8)).toEqual(["Sim", "Não"]);
    expect(cellsOf(wrapper, 1).slice(6, 8)).toEqual(["Não", "Sim"]);
  });

  it("mostra a pendência via PendingBadge: pronto para avançar ou lista do que falta", () => {
    const wrapper = mount(LegalTable, {
      props: {
        rows: [
          row(),
          row({
            equipmentId: "eq-2",
            pending: [{ code: "contract_number", field: "contractNumber", message: "Informar o número do contrato" }],
          }),
        ],
      },
      global: globalStubs,
    });
    expect(cellsOf(wrapper, 0)[11]).toContain("Pronto para Escrituração do contrato");
    expect(cellsOf(wrapper, 1)[11]).toContain("Falta para avançar");
    expect(cellsOf(wrapper, 1)[11]).toContain("Informar o número do contrato");
  });

  it("aponta o link Ver detalhes para /equipamentos/{id}", () => {
    const wrapper = mount(LegalTable, { props: { rows: [row({ equipmentId: "eq-42" })] }, global: globalStubs });
    const link = wrapper.get("a");
    expect(link.attributes("href")).toBe("/equipamentos/eq-42");
    expect(link.text()).toBe("Ver detalhes");
  });

  it("renderiza uma linha por equipamento, na ordem recebida", () => {
    const rows = [
      row({ equipmentId: "eq-1", equipmentName: "Bomba Sintética A" }),
      row({ equipmentId: "eq-2", equipmentName: "Compressor" }),
      row({ equipmentId: "eq-3", equipmentName: "Motor" }),
    ];
    const wrapper = mount(LegalTable, { props: { rows }, global: globalStubs });
    expect(wrapper.findAll("a").map((item) => item.attributes("href"))).toEqual([
      "/equipamentos/eq-1",
      "/equipamentos/eq-2",
      "/equipamentos/eq-3",
    ]);
    expect([0, 1, 2].map((index) => cellsOf(wrapper, index)[0])).toEqual(["Bomba Sintética A", "Compressor", "Motor"]);
  });

  it("campos opcionais nulos viram travessão", () => {
    const partial = row({
      responsibleUser: null,
      ticketNumber: null,
      openedAt: null,
      contractNumber: null,
      executedAt: null,
      deliveryAt: null,
    });
    const wrapper = mount(LegalTable, { props: { rows: [partial] }, global: globalStubs });
    const cells = cellsOf(wrapper);
    expect([cells[2], cells[4], cells[5], cells[8], cells[9], cells[10]]).toEqual(["—", "—", "—", "—", "—", "—"]);
  });

  it("sem linhas renderiza só o cabeçalho", () => {
    const wrapper = mount(LegalTable, { props: { rows: [] }, global: globalStubs });
    expect(wrapper.findAll(".head")).toHaveLength(13);
    expect(wrapper.findAll(".cell")).toHaveLength(0);
  });
});
