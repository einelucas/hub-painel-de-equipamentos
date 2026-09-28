import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import EquipmentContractsTable from "~/components/equipment/contracts/EquipmentContractsTable.vue";
import type { Contract } from "~/types/equipment";

const passthrough = { template: "<div><slot /></div>" };
const stubs = {
  Table: passthrough,
  TableHeader: passthrough,
  TableBody: passthrough,
  TableRow: { template: "<div class='row'><slot /></div>" },
  TableHead: { template: "<div class='head'><slot /></div>" },
  TableCell: { template: "<div class='cell'><slot /></div>" },
};

function contract(overrides: Partial<Contract> = {}): Contract {
  return {
    id: "ct-1",
    equipmentId: "eq-1",
    contractNumber: "CT-0001",
    executedAt: "2026-03-01",
    file: {
      fileName: "contrato.pdf",
      fileContentType: "application/pdf",
      fileSizeBytes: 1024,
      fileUploadedBy: null,
      fileUploadedAt: null,
    },
    createdAt: "2026-03-01T00:00:00",
    updatedAt: "2026-03-01T00:00:00",
    ...overrides,
  };
}

function mountTable(contracts: Contract[], editable = true, busy = false) {
  return mount(EquipmentContractsTable, {
    props: { contracts, editable, busy },
    global: { stubs },
  });
}

function cellsOf(wrapper: ReturnType<typeof mountTable>, id: string): string[] {
  return wrapper.get(`[data-testid='contract-${id}']`).findAll(".cell").map((item) => item.text());
}

describe("EquipmentContractsTable", () => {
  it("renderiza cabeçalho e um contrato com número, data formatada e arquivo", () => {
    const wrapper = mountTable([contract()]);
    expect(wrapper.findAll(".head").map((item) => item.text())).toEqual(["Número", "Escrituração", "Arquivo", ""]);
    const cells = cellsOf(wrapper, "ct-1");
    expect(cells[0]).toBe("CT-0001");
    expect(cells[1]).toBe("01/03/2026");
    expect(cells[2]).toBe("contrato.pdf");
  });

  it("renderiza vários contratos na ordem recebida", () => {
    const wrapper = mountTable([
      contract({ id: "ct-1", contractNumber: "CT-0001" }),
      contract({ id: "ct-2", contractNumber: "CT-0002" }),
      contract({ id: "ct-3", contractNumber: "CT-0003" }),
    ]);
    const ids = wrapper.findAll("[data-testid^='contract-']").map((item) => item.attributes("data-testid"));
    expect(ids).toEqual(["contract-ct-1", "contract-ct-2", "contract-ct-3"]);
  });

  it("contrato sem número, sem data e sem arquivo mostra travessões e nenhum botão de download", () => {
    const wrapper = mountTable([contract({ contractNumber: null, executedAt: null, file: null })]);
    const cells = cellsOf(wrapper, "ct-1");
    expect(cells.slice(0, 3)).toEqual(["—", "—", "—"]);
    expect(wrapper.findAll("button").map((item) => item.text())).not.toContain("contrato.pdf");
  });

  it("mostra o estado vazio quando não há contratos", () => {
    const wrapper = mountTable([]);
    expect(wrapper.get("[data-testid='contracts-empty']").text()).toContain("Nenhum contrato cadastrado");
    expect(wrapper.findAll(".row")).toHaveLength(0);
  });

  it("emite download, edit e delete com o contrato da linha clicada", async () => {
    const second = contract({ id: "ct-2", contractNumber: "CT-0002" });
    const wrapper = mountTable([contract(), second]);
    const row = wrapper.get("[data-testid='contract-ct-2']");
    const button = (label: string) => row.findAll("button").find((item) => item.text().includes(label))!;

    await button("contrato.pdf").trigger("click");
    await button("Editar").trigger("click");
    await button("Excluir").trigger("click");

    expect(wrapper.emitted("download")).toEqual([[second]]);
    expect(wrapper.emitted("edit")).toEqual([[second]]);
    expect(wrapper.emitted("delete")).toEqual([[second]]);
  });

  it("editable=false oculta Editar e Excluir, mas mantém o download do arquivo", () => {
    const wrapper = mountTable([contract()], false);
    const labels = wrapper.findAll("button").map((item) => item.text());
    expect(labels).toEqual(["contrato.pdf"]);
  });

  it("busy desabilita o Excluir", () => {
    const wrapper = mountTable([contract()], true, true);
    const remove = wrapper.findAll("button").find((item) => item.text().includes("Excluir"))!;
    expect(remove.attributes("disabled")).toBeDefined();
  });
});
