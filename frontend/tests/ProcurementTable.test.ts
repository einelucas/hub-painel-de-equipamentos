import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import ProcurementTable from "~/components/queue/ProcurementTable.vue";
import ProcurementTableHeader from "~/components/queue/ProcurementTableHeader.vue";
import ProcurementTableRow from "~/components/queue/ProcurementTableRow.vue";
import PendingBadge from "~/components/queue/PendingBadge.vue";
import type { ProcurementRow } from "~/types/equipment";

const passthrough = { template: "<div><slot /></div>" };
const globalStubs = {
  components: { ProcurementTableHeader, ProcurementTableRow, PendingBadge },
  stubs: {
    Table: passthrough,
    TableHeader: passthrough,
    TableBody: passthrough,
    TableRow: { template: "<div class='row'><slot /></div>" },
    TableHead: { template: "<div class='head'><slot /></div>" },
    TableCell: { template: "<div class='cell'><slot /></div>" },
    NuxtLink: { props: ["to"], template: "<a :href='to'><slot /></a>" },
  },
};

const COL = {
  equipment: 0,
  unit: 1,
  responsible: 2,
  stage: 3,
  kind: 4,
  requestNumber: 5,
  requestedAt: 6,
  orderNumber: 7,
  orderedAt: 8,
  amount: 9,
  supplier: 10,
  pending: 11,
} as const;

function row(overrides: Partial<ProcurementRow> = {}): ProcurementRow {
  return {
    equipmentId: "eq-1",
    equipmentName: "Bomba SUMP",
    unit: { id: "unit-1", code: "LEM", name: "Luís Eduardo Magalhães" },
    projectContext: { id: "ctx-1", code: "C2", name: "Caldeira 2" },
    currentStage: 7,
    currentStageName: "Aprovação da OC",
    nextStage: 8,
    nextStageName: "Concluído",
    pending: [],
    responsibleUser: { id: "u-1", name: "Ana Carolina", email: "ana@inpasa.com.br" },
    primarySupplier: { id: "s-1", legalName: "Metalúrgica Alfa Ltda", tradeName: "Alfa" },
    kind: "SC",
    requestNumber: "SC-4455",
    requestedAt: "2027-05-10",
    orderNumber: "OC-7788",
    orderedAt: "2027-06-01",
    amount: "150000.5",
    ...overrides,
  };
}

function cellsOf(wrapper: ReturnType<typeof mount>, index = 0): string[] {
  const bodyRows = wrapper.findAll(".row").filter((item) => item.findAll(".cell").length > 0);
  return bodyRows[index]!.findAll(".cell").map((item) => item.text());
}

describe("ProcurementTable", () => {
  it("renderiza exatamente as colunas atuais da fila de suprimentos", () => {
    const wrapper = mount(ProcurementTable, { props: { rows: [row()] }, global: globalStubs });
    expect(wrapper.findAll(".head").map((item) => item.text())).toEqual([
      "Equipamento",
      "Unidade",
      "Responsável",
      "Etapa",
      "Tipo",
      "Número SC/OCI",
      "Data SC/OCI",
      "Número OC",
      "Data OC",
      "Valor OC",
      "Fornecedor principal",
      "Pendência",
      "",
    ]);
  });

  it("renderiza um ProcurementRow com equipamento, unidade, responsável, etapa, tipo e fornecedor", () => {
    const wrapper = mount(ProcurementTable, { props: { rows: [row()] }, global: globalStubs });
    const cells = cellsOf(wrapper);
    expect(cells[COL.equipment]).toBe("Bomba SUMP");
    expect(cells[COL.unit]).toBe("LEM");
    expect(cells[COL.responsible]).toBe("Ana Carolina");
    expect(cells[COL.stage]).toBe("7 · Aprovação da OC");
    expect(cells[COL.kind]).toBe("SC");
    expect(cells[COL.supplier]).toBe("Metalúrgica Alfa Ltda");
  });

  it("exibe a etapa com o mesmo selo colorido das outras filas", () => {
    const wrapper = mount(ProcurementTable, { props: { rows: [row()] }, global: globalStubs });
    const badge = wrapper.get(".stage-badge");
    expect(badge.text()).toBe("7 · Aprovação da OC");
    expect(badge.classes()).toContain("stage-badge--advanced");
  });

  it("exibe número e data da SC/OCI e da OC, com datas formatadas", () => {
    const wrapper = mount(ProcurementTable, { props: { rows: [row({ kind: "OCI" })] }, global: globalStubs });
    const cells = cellsOf(wrapper);
    expect(cells[COL.kind]).toBe("OCI");
    expect(cells[COL.requestNumber]).toBe("SC-4455");
    expect(cells[COL.requestedAt]).toBe("10/05/2027");
    expect(cells[COL.orderNumber]).toBe("OC-7788");
    expect(cells[COL.orderedAt]).toBe("01/06/2027");
  });

  it("formata o valor da OC em reais, aceitando string ou número", () => {
    const wrapper = mount(ProcurementTable, {
      props: { rows: [row(), row({ equipmentId: "eq-2", amount: 2500 })] },
      global: globalStubs,
    });
    expect(cellsOf(wrapper, 0)[COL.amount]).toMatch(/^R\$\s150\.000,50$/);
    expect(cellsOf(wrapper, 1)[COL.amount]).toMatch(/^R\$\s2\.500,00$/);
  });

  it("mostra a pendência via PendingBadge: pronto, faltando itens ou concluído", () => {
    const wrapper = mount(ProcurementTable, {
      props: {
        rows: [
          row(),
          row({
            equipmentId: "eq-2",
            pending: [{ code: "order_number", field: "orderNumber", message: "Informar o número da OC" }],
          }),
          row({ equipmentId: "eq-3", nextStage: null, nextStageName: null }),
        ],
      },
      global: globalStubs,
    });
    expect(cellsOf(wrapper, 0)[COL.pending]).toContain("Pronto para Concluído");
    expect(cellsOf(wrapper, 1)[COL.pending]).toContain("Falta para avançar");
    expect(cellsOf(wrapper, 1)[COL.pending]).toContain("Informar o número da OC");
    expect(cellsOf(wrapper, 2)[COL.pending]).toContain("Processo concluído");
  });

  it("aponta o link Ver detalhes para /equipamentos/{id}", () => {
    const wrapper = mount(ProcurementTable, { props: { rows: [row({ equipmentId: "eq-42" })] }, global: globalStubs });
    const link = wrapper.get("a");
    expect(link.attributes("href")).toBe("/equipamentos/eq-42");
    expect(link.text()).toBe("Ver detalhes");
  });

  it("renderiza uma linha por equipamento, na ordem recebida", () => {
    const rows = [
      row({ equipmentId: "eq-1", equipmentName: "Bomba SUMP" }),
      row({ equipmentId: "eq-2", equipmentName: "Compressor" }),
      row({ equipmentId: "eq-3", equipmentName: "Motor" }),
    ];
    const wrapper = mount(ProcurementTable, { props: { rows }, global: globalStubs });
    expect(wrapper.findAll("a").map((item) => item.attributes("href"))).toEqual([
      "/equipamentos/eq-1",
      "/equipamentos/eq-2",
      "/equipamentos/eq-3",
    ]);
    expect([0, 1, 2].map((index) => cellsOf(wrapper, index)[COL.equipment])).toEqual(["Bomba SUMP", "Compressor", "Motor"]);
  });

  it("campos opcionais nulos viram travessão", () => {
    const partial = row({
      responsibleUser: null,
      primarySupplier: null,
      kind: null,
      requestNumber: null,
      requestedAt: null,
      orderNumber: null,
      orderedAt: null,
      amount: null,
    });
    const wrapper = mount(ProcurementTable, { props: { rows: [partial] }, global: globalStubs });
    const cells = cellsOf(wrapper);
    expect([
      cells[COL.responsible],
      cells[COL.kind],
      cells[COL.requestNumber],
      cells[COL.requestedAt],
      cells[COL.orderNumber],
      cells[COL.orderedAt],
      cells[COL.amount],
      cells[COL.supplier],
    ]).toEqual(["—", "—", "—", "—", "—", "—", "—", "—"]);
  });

  it("sem linhas renderiza só o cabeçalho", () => {
    const wrapper = mount(ProcurementTable, { props: { rows: [] }, global: globalStubs });
    expect(wrapper.findAll(".head")).toHaveLength(13);
    expect(wrapper.findAll(".cell")).toHaveLength(0);
  });
});
