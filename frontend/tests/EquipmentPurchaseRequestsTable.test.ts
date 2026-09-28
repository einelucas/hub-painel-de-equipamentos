import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import EquipmentPurchaseRequestsTable from "~/components/equipment/purchase-requests/EquipmentPurchaseRequestsTable.vue";
import type { PurchaseRequest } from "~/types/equipment";

const passthrough = { template: "<div><slot /></div>" };
const stubs = {
  Table: passthrough,
  TableHeader: passthrough,
  TableBody: passthrough,
  TableRow: { template: "<div class='row'><slot /></div>" },
  TableHead: { template: "<div class='head'><slot /></div>" },
  TableCell: { template: "<div class='cell'><slot /></div>" },
};

function request(overrides: Partial<PurchaseRequest> = {}): PurchaseRequest {
  return {
    id: "pr-1",
    equipmentId: "eq-1",
    kind: "SC",
    requestNumber: "SC-4455",
    requestedAt: "2027-05-10",
    createdAt: "2027-05-10T00:00:00",
    updatedAt: "2027-05-10T00:00:00",
    ...overrides,
  };
}

function mountTable(items: PurchaseRequest[], editable = true, busy = false) {
  return mount(EquipmentPurchaseRequestsTable, {
    props: { items, editable, busy },
    global: { stubs },
  });
}

function cellsOf(wrapper: ReturnType<typeof mountTable>, id: string): string[] {
  return wrapper.get(`[data-testid='purchase-request-${id}']`).findAll(".cell").map((item) => item.text());
}

describe("EquipmentPurchaseRequestsTable", () => {
  it("renderiza cabeçalho e uma SC com tipo, número e data formatada", () => {
    const wrapper = mountTable([request()]);
    expect(wrapper.findAll(".head").map((item) => item.text())).toEqual(["Tipo", "Número", "Data", ""]);
    expect(cellsOf(wrapper, "pr-1").slice(0, 3)).toEqual(["SC", "SC-4455", "10/05/2027"]);
  });

  it("renderiza uma OCI", () => {
    const wrapper = mountTable([request({ kind: "OCI", requestNumber: "OCI-12" })]);
    expect(cellsOf(wrapper, "pr-1").slice(0, 2)).toEqual(["OCI", "OCI-12"]);
  });

  it("renderiza várias SC/OCI na ordem recebida", () => {
    const wrapper = mountTable([
      request({ id: "pr-1" }),
      request({ id: "pr-2", kind: "OCI" }),
      request({ id: "pr-3" }),
    ]);
    const ids = wrapper.findAll("[data-testid^='purchase-request-']").map((item) => item.attributes("data-testid"));
    expect(ids).toEqual(["purchase-request-pr-1", "purchase-request-pr-2", "purchase-request-pr-3"]);
  });

  it("tipo, número e data vazios viram travessão", () => {
    const wrapper = mountTable([request({ kind: null, requestNumber: null, requestedAt: null })]);
    expect(cellsOf(wrapper, "pr-1").slice(0, 3)).toEqual(["—", "—", "—"]);
  });

  it("mostra o estado vazio quando não há SC/OCI", () => {
    const wrapper = mountTable([]);
    expect(wrapper.get("[data-testid='purchase-requests-empty']").text()).toContain("Nenhuma SC/OCI cadastrada");
    expect(wrapper.findAll(".row")).toHaveLength(0);
  });

  it("emite edit e delete com o item da linha clicada", async () => {
    const second = request({ id: "pr-2", requestNumber: "SC-0002" });
    const wrapper = mountTable([request(), second]);
    const row = wrapper.get("[data-testid='purchase-request-pr-2']");
    const button = (label: string) => row.findAll("button").find((item) => item.text().includes(label))!;

    await button("Editar").trigger("click");
    await button("Excluir").trigger("click");

    expect(wrapper.emitted("edit")).toEqual([[second]]);
    expect(wrapper.emitted("delete")).toEqual([[second]]);
  });

  it("editable=false oculta Editar e Excluir", () => {
    const wrapper = mountTable([request()], false);
    expect(wrapper.findAll("button")).toHaveLength(0);
  });

  it("busy desabilita o Excluir", () => {
    const wrapper = mountTable([request()], true, true);
    const remove = wrapper.findAll("button").find((item) => item.text().includes("Excluir"))!;
    expect(remove.attributes("disabled")).toBeDefined();
  });
});
