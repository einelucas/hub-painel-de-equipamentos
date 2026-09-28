import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import EquipmentPurchaseOrdersTable from "~/components/equipment/purchase-orders/EquipmentPurchaseOrdersTable.vue";
import type { PurchaseOrder } from "~/types/equipment";

const passthrough = { template: "<div><slot /></div>" };
const stubs = {
  Table: passthrough,
  TableHeader: passthrough,
  TableBody: passthrough,
  TableRow: { template: "<div class='row'><slot /></div>" },
  TableHead: { template: "<div class='head'><slot /></div>" },
  TableCell: { template: "<div class='cell'><slot /></div>" },
};

function order(overrides: Partial<PurchaseOrder> = {}): PurchaseOrder {
  return {
    id: "po-1",
    equipmentId: "eq-1",
    orderNumber: "OC-7788",
    orderedAt: "2027-06-01",
    amount: "150000.50",
    createdAt: "2027-06-01T00:00:00",
    updatedAt: "2027-06-01T00:00:00",
    ...overrides,
  };
}

function mountTable(items: PurchaseOrder[], editable = true, busy = false) {
  return mount(EquipmentPurchaseOrdersTable, {
    props: { items, editable, busy },
    global: { stubs },
  });
}

function cellsOf(wrapper: ReturnType<typeof mountTable>, id: string): string[] {
  return wrapper.get(`[data-testid='purchase-order-${id}']`).findAll(".cell").map((item) => item.text());
}

describe("EquipmentPurchaseOrdersTable", () => {
  it("renderiza cabeçalho e uma OC com número, data e valor formatados", () => {
    const wrapper = mountTable([order()]);
    expect(wrapper.findAll(".head").map((item) => item.text())).toEqual(["Número", "Data", "Valor", ""]);
    const cells = cellsOf(wrapper, "po-1");
    expect(cells[0]).toBe("OC-7788");
    expect(cells[1]).toBe("01/06/2027");
    expect(cells[2]).toMatch(/^R\$\s150\.000,50$/);
  });

  it("formata valor numérico da API da mesma forma que valor em texto", () => {
    const wrapper = mountTable([order({ amount: 2500 })]);
    expect(cellsOf(wrapper, "po-1")[2]).toMatch(/^R\$\s2\.500,00$/);
  });

  it("renderiza várias OCs na ordem recebida", () => {
    const wrapper = mountTable([order({ id: "po-1" }), order({ id: "po-2" }), order({ id: "po-3" })]);
    const ids = wrapper.findAll("[data-testid^='purchase-order-']").map((item) => item.attributes("data-testid"));
    expect(ids).toEqual(["purchase-order-po-1", "purchase-order-po-2", "purchase-order-po-3"]);
  });

  it("número, data e valor ausentes viram travessão", () => {
    const wrapper = mountTable([order({ orderNumber: null, orderedAt: null, amount: null })]);
    expect(cellsOf(wrapper, "po-1").slice(0, 3)).toEqual(["—", "—", "—"]);
  });

  it("mostra o estado vazio com o aviso da Fase 7 → 8", () => {
    const wrapper = mountTable([]);
    const empty = wrapper.get("[data-testid='purchase-orders-empty']");
    expect(empty.text()).toContain("Nenhuma OC cadastrada");
    expect(empty.text()).toContain("Fase 7 → 8");
    expect(wrapper.findAll(".row")).toHaveLength(0);
  });

  it("emite edit e delete com a OC da linha clicada", async () => {
    const second = order({ id: "po-2", orderNumber: "OC-0002" });
    const wrapper = mountTable([order(), second]);
    const row = wrapper.get("[data-testid='purchase-order-po-2']");
    const button = (label: string) => row.findAll("button").find((item) => item.text().includes(label))!;

    await button("Editar").trigger("click");
    await button("Excluir").trigger("click");

    expect(wrapper.emitted("edit")).toEqual([[second]]);
    expect(wrapper.emitted("delete")).toEqual([[second]]);
  });

  it("editable=false oculta Editar e Excluir", () => {
    const wrapper = mountTable([order()], false);
    expect(wrapper.findAll("button")).toHaveLength(0);
  });

  it("busy desabilita o Excluir", () => {
    const wrapper = mountTable([order()], true, true);
    const remove = wrapper.findAll("button").find((item) => item.text().includes("Excluir"))!;
    expect(remove.attributes("disabled")).toBeDefined();
  });
});
