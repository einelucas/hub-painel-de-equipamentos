import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import EquipmentPurchaseRequestForm from "~/components/equipment/purchase-requests/EquipmentPurchaseRequestForm.vue";
import EquipmentPurchaseRequestsList from "~/components/equipment/EquipmentPurchaseRequestsList.vue";
import type { PurchaseRequest, RequirementGroup } from "~/types/equipment";

const existing: PurchaseRequest = {
  id: "pr-1",
  equipmentId: "eq-1",
  kind: "OCI",
  requestNumber: "OCI-12",
  requestedAt: "2027-05-10",
  createdAt: "2027-05-10T00:00:00",
  updatedAt: "2027-05-10T00:00:00",
};

function mountForm(item: PurchaseRequest | null, props: { busy?: boolean; error?: string } = {}) {
  return mount(EquipmentPurchaseRequestForm, {
    props: { item, busy: props.busy ?? false, error: props.error ?? "" },
  });
}

function fields(wrapper: ReturnType<typeof mount>) {
  return {
    kind: wrapper.get("select"),
    number: wrapper.get("input:not([type='date'])"),
    date: wrapper.get("input[type='date']"),
  };
}

describe("EquipmentPurchaseRequestForm", () => {
  it("criação: tipo Não informado e campos vazios", () => {
    const { kind, number, date } = fields(mountForm(null));
    expect((kind.element as HTMLSelectElement).value).toBe("");
    expect(kind.findAll("option").map((item) => item.text())).toEqual(["Não informado", "SC", "OCI"]);
    expect((number.element as HTMLInputElement).value).toBe("");
    expect((date.element as HTMLInputElement).value).toBe("");
  });

  it("edição: campos preenchidos com a SC/OCI recebida", () => {
    const { kind, number, date } = fields(mountForm(existing));
    expect((kind.element as HTMLSelectElement).value).toBe("OCI");
    expect((number.element as HTMLInputElement).value).toBe("OCI-12");
    expect((date.element as HTMLInputElement).value).toBe("2027-05-10");
  });

  it("submit emite os valores digitados", async () => {
    const wrapper = mountForm(null);
    const { kind, number, date } = fields(wrapper);
    await kind.setValue("SC");
    await number.setValue("SC-0099");
    await date.setValue("2027-06-01");

    await wrapper.get("form").trigger("submit");

    expect(wrapper.emitted("submit")).toEqual([[{ kind: "SC", requestNumber: "SC-0099", requestedAt: "2027-06-01" }]]);
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

describe("EquipmentPurchaseRequestsList (container)", () => {
  afterEach(() => vi.unstubAllGlobals());

  const passthrough = { template: "<div><slot /></div>" };
  const listStubs = {
    AppModal: { props: ["open", "title"], template: "<div v-if='open' class='modal'><h2>{{ title }}</h2><slot /></div>" },
    RequirementWaiverBanner: { props: ["equipmentId", "stage", "group", "waiver"], template: "<div class='waiver-stub'>{{ stage }}</div>" },
    Table: passthrough,
    TableHeader: passthrough,
    TableBody: passthrough,
    TableRow: passthrough,
    TableHead: passthrough,
    TableCell: passthrough,
  };

  function mountList(items: PurchaseRequest[], api: Record<string, unknown>, extra: Record<string, unknown> = {}) {
    vi.stubGlobal("useApi", () => ({ post: vi.fn(), patch: vi.fn(), delete: vi.fn(), ...api }));
    return mount(EquipmentPurchaseRequestsList, {
      props: { equipmentId: "eq-1", items, editable: true, ...extra },
      global: { stubs: listStubs },
    });
  }

  it("cria via POST convertendo tipo vazio e campos em branco para null", async () => {
    const post = vi.fn().mockResolvedValue(existing);
    const wrapper = mountList([], { post });

    await wrapper.get("[data-testid='add-purchase-request']").trigger("click");
    expect(wrapper.get(".modal h2").text()).toBe("Nova SC/OCI");
    await wrapper.get(".modal input:not([type='date'])").setValue("SC-0099");
    await wrapper.get(".modal form").trigger("submit");
    await flushPromises();

    expect(post).toHaveBeenCalledWith("/equipments/eq-1/purchase-requests", {
      kind: null,
      requestNumber: "SC-0099",
      requestedAt: null,
    });
    expect(wrapper.emitted("changed")).toHaveLength(1);
    expect(wrapper.find(".modal").exists()).toBe(false);
  });

  it("edita via PATCH com os valores atuais do item", async () => {
    const patch = vi.fn().mockResolvedValue(existing);
    const wrapper = mountList([existing], { patch });

    await wrapper.findAll("button").find((item) => item.text().includes("Editar"))!.trigger("click");
    expect(wrapper.get(".modal h2").text()).toBe("Editar SC/OCI");
    await wrapper.get(".modal form").trigger("submit");
    await flushPromises();

    expect(patch).toHaveBeenCalledWith("/equipments/eq-1/purchase-requests/pr-1", {
      kind: "OCI",
      requestNumber: "OCI-12",
      requestedAt: "2027-05-10",
    });
    expect(wrapper.emitted("changed")).toHaveLength(1);
  });

  it("erro ao salvar mantém o modal aberto e mostra a mensagem", async () => {
    const post = vi.fn().mockRejectedValue(new Error("Número duplicado"));
    const wrapper = mountList([], { post });

    await wrapper.get("[data-testid='add-purchase-request']").trigger("click");
    await wrapper.get(".modal form").trigger("submit");
    await flushPromises();

    expect(wrapper.find(".modal").exists()).toBe(true);
    expect(wrapper.get(".modal [role='alert']").text()).toBe("Número duplicado");
    expect(wrapper.emitted("changed")).toBeUndefined();
  });

  it("exclui via DELETE e mostra o erro da API na seção quando falha", async () => {
    const del = vi.fn().mockRejectedValue(new Error("SC vinculada"));
    const wrapper = mountList([existing], { delete: del });

    await wrapper.findAll("button").find((item) => item.text().includes("Excluir"))!.trigger("click");
    await flushPromises();

    expect(del).toHaveBeenCalledWith("/equipments/eq-1/purchase-requests/pr-1");
    expect(wrapper.get(".list-notice").text()).toBe("SC vinculada");
    expect(wrapper.emitted("changed")).toBeUndefined();
  });

  it("mostra o banner de dispensa só quando há grupo e fase, ou uma dispensa ativa", () => {
    const group: RequirementGroup = {
      code: "PURCHASE_REQUEST",
      label: "SC/OCI",
      status: "MISSING",
      waivable: true,
      fields: [],
      message: "",
      waiver: null,
    };
    expect(mountList([], {}).find(".waiver-stub").exists()).toBe(false);
    expect(mountList([], {}, { requirementGroup: group }).find(".waiver-stub").exists()).toBe(false);
    expect(mountList([], {}, { requirementGroup: group, requirementStage: 6 }).get(".waiver-stub").text()).toBe("6");
  });

  it("editable=false esconde o botão Adicionar", () => {
    const wrapper = mountList([existing], {}, { editable: false });
    expect(wrapper.find("[data-testid='add-purchase-request']").exists()).toBe(false);
  });
});
