import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import EquipmentPurchaseOrderForm from "~/components/equipment/purchase-orders/EquipmentPurchaseOrderForm.vue";
import EquipmentPurchaseOrdersList from "~/components/equipment/EquipmentPurchaseOrdersList.vue";
import type { PurchaseOrder } from "~/types/equipment";

const existing: PurchaseOrder = {
  id: "po-1",
  equipmentId: "eq-1",
  orderNumber: "OC-7788",
  orderedAt: "2027-06-01",
  amount: "150000.50",
  createdAt: "2027-06-01T00:00:00",
  updatedAt: "2027-06-01T00:00:00",
};

function mountForm(item: PurchaseOrder | null, props: { busy?: boolean; error?: string } = {}) {
  return mount(EquipmentPurchaseOrderForm, {
    props: { item, busy: props.busy ?? false, error: props.error ?? "" },
  });
}

function fields(wrapper: ReturnType<typeof mount>) {
  const [number, date, amount] = wrapper.findAll("input");
  return { number: number!, date: date!, amount: amount! };
}

describe("EquipmentPurchaseOrderForm", () => {
  it("criação: campos vazios e valor numérico com mínimo 0 e centavos", () => {
    const { number, date, amount } = fields(mountForm(null));
    expect((number.element as HTMLInputElement).value).toBe("");
    expect((date.element as HTMLInputElement).value).toBe("");
    expect((amount.element as HTMLInputElement).value).toBe("");
    expect(amount.attributes()).toMatchObject({ type: "number", min: "0", step: "0.01" });
  });

  it("edição: campos preenchidos com a OC recebida", () => {
    const { number, date, amount } = fields(mountForm(existing));
    expect((number.element as HTMLInputElement).value).toBe("OC-7788");
    expect((date.element as HTMLInputElement).value).toBe("2027-06-01");
    expect((amount.element as HTMLInputElement).value).toBe("150000.50");
  });

  it("edição de OC sem valor deixa o campo Valor vazio", () => {
    const { amount } = fields(mountForm({ ...existing, amount: null }));
    expect((amount.element as HTMLInputElement).value).toBe("");
  });

  it("submit emite número, data e valor digitados", async () => {
    const wrapper = mountForm(null);
    const { number, date, amount } = fields(wrapper);
    await number.setValue("OC-0099");
    await date.setValue("2027-07-15");
    await amount.setValue("1500.5");

    await wrapper.get("form").trigger("submit");

    const [[values]] = wrapper.emitted("submit") as [[{ orderNumber: string; orderedAt: string; amount: string | number }]];
    expect(values.orderNumber).toBe("OC-0099");
    expect(values.orderedAt).toBe("2027-07-15");
    expect(Number(values.amount)).toBe(1500.5);
  });

  it("Cancelar emite cancel sem submit", async () => {
    const wrapper = mountForm(existing);
    await wrapper.findAll("button").find((item) => item.text() === "Cancelar")!.trigger("click");
    expect(wrapper.emitted("cancel")).toHaveLength(1);
    expect(wrapper.emitted("submit")).toBeUndefined();
  });

  it("busy desabilita Salvar e mostra Salvando...; erro aparece no formulário", () => {
    const wrapper = mountForm(null, { busy: true, error: "Falhou" });
    const save = wrapper.get("button[type='submit']");
    expect(save.text()).toBe("Salvando...");
    expect(save.attributes("disabled")).toBeDefined();
    expect(wrapper.get("[role='alert']").text()).toBe("Falhou");
  });
});

describe("EquipmentPurchaseOrdersList (container)", () => {
  afterEach(() => vi.unstubAllGlobals());

  const passthrough = { template: "<div><slot /></div>" };
  const listStubs = {
    AppModal: { props: ["open", "title"], template: "<div v-if='open' class='modal'><h2>{{ title }}</h2><slot /></div>" },
    Table: passthrough,
    TableHeader: passthrough,
    TableBody: passthrough,
    TableRow: passthrough,
    TableHead: passthrough,
    TableCell: passthrough,
  };

  function mountList(items: PurchaseOrder[], api: Record<string, unknown>, editable = true) {
    vi.stubGlobal("useApi", () => ({ post: vi.fn(), patch: vi.fn(), delete: vi.fn(), ...api }));
    return mount(EquipmentPurchaseOrdersList, {
      props: { equipmentId: "eq-1", items, editable },
      global: { stubs: listStubs },
    });
  }

  it("cria via POST enviando amount como número", async () => {
    const post = vi.fn().mockResolvedValue(existing);
    const wrapper = mountList([], { post });

    await wrapper.get("[data-testid='add-purchase-order']").trigger("click");
    expect(wrapper.get(".modal h2").text()).toBe("Nova ordem de compra");
    const [number, , amount] = wrapper.findAll(".modal input");
    await number!.setValue("OC-0099");
    await amount!.setValue("1500.5");
    await wrapper.get(".modal form").trigger("submit");
    await flushPromises();

    expect(post).toHaveBeenCalledWith("/equipments/eq-1/purchase-orders", {
      orderNumber: "OC-0099",
      orderedAt: null,
      amount: 1500.5,
    });
    expect(wrapper.emitted("changed")).toHaveLength(1);
    expect(wrapper.find(".modal").exists()).toBe(false);
  });

  it("valor vazio vira amount null no payload", async () => {
    const post = vi.fn().mockResolvedValue(existing);
    const wrapper = mountList([], { post });

    await wrapper.get("[data-testid='add-purchase-order']").trigger("click");
    await wrapper.get(".modal form").trigger("submit");
    await flushPromises();

    expect(post).toHaveBeenCalledWith("/equipments/eq-1/purchase-orders", {
      orderNumber: null,
      orderedAt: null,
      amount: null,
    });
  });

  it("edita via PATCH convertendo o valor em texto vindo da API para número", async () => {
    const patch = vi.fn().mockResolvedValue(existing);
    const wrapper = mountList([existing], { patch });

    await wrapper.findAll("button").find((item) => item.text().includes("Editar"))!.trigger("click");
    expect(wrapper.get(".modal h2").text()).toBe("Editar ordem de compra");
    await wrapper.get(".modal form").trigger("submit");
    await flushPromises();

    expect(patch).toHaveBeenCalledWith("/equipments/eq-1/purchase-orders/po-1", {
      orderNumber: "OC-7788",
      orderedAt: "2027-06-01",
      amount: 150000.5,
    });
    expect(wrapper.emitted("changed")).toHaveLength(1);
  });

  it("erro ao salvar mantém o modal aberto e mostra a mensagem", async () => {
    const post = vi.fn().mockRejectedValue(new Error("Valor inválido"));
    const wrapper = mountList([], { post });

    await wrapper.get("[data-testid='add-purchase-order']").trigger("click");
    await wrapper.get(".modal form").trigger("submit");
    await flushPromises();

    expect(wrapper.find(".modal").exists()).toBe(true);
    expect(wrapper.get(".modal [role='alert']").text()).toBe("Valor inválido");
    expect(wrapper.emitted("changed")).toBeUndefined();
  });

  it("exclui via DELETE e mostra o erro da API na seção quando falha", async () => {
    const del = vi.fn().mockRejectedValue(new Error("OC vinculada"));
    const wrapper = mountList([existing], { delete: del });

    await wrapper.findAll("button").find((item) => item.text().includes("Excluir"))!.trigger("click");
    await flushPromises();

    expect(del).toHaveBeenCalledWith("/equipments/eq-1/purchase-orders/po-1");
    expect(wrapper.get(".list-notice").text()).toBe("OC vinculada");
    expect(wrapper.emitted("changed")).toBeUndefined();
  });

  it("ordena as OCs por data de criação", () => {
    const newer = { ...existing, id: "po-new", createdAt: "2027-08-01T00:00:00" };
    const older = { ...existing, id: "po-old", createdAt: "2027-01-01T00:00:00" };
    const wrapper = mountList([newer, older], {});
    const ids = wrapper.findAll("[data-testid^='purchase-order-']").map((item) => item.attributes("data-testid"));
    expect(ids).toEqual(["purchase-order-po-old", "purchase-order-po-new"]);
  });

  it("editable=false esconde o botão Adicionar", () => {
    const wrapper = mountList([existing], {}, false);
    expect(wrapper.find("[data-testid='add-purchase-order']").exists()).toBe(false);
  });
});
