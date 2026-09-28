import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import EquipmentContractForm from "~/components/equipment/contracts/EquipmentContractForm.vue";
import EquipmentContractsList from "~/components/equipment/EquipmentContractsList.vue";
import type { Contract } from "~/types/equipment";

const existing: Contract = {
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
};

function mountForm(contract: Contract | null, props: { busy?: boolean; error?: string } = {}) {
  return mount(EquipmentContractForm, {
    props: { contract, busy: props.busy ?? false, error: props.error ?? "" },
  });
}

async function chooseFile(wrapper: ReturnType<typeof mount>, file: File): Promise<void> {
  const input = wrapper.get("input[type='file']");
  Object.defineProperty(input.element, "files", { value: [file], configurable: true });
  await input.trigger("change");
}

describe("EquipmentContractForm", () => {
  it("criação: campos vazios e botão de arquivo pedindo seleção", () => {
    const wrapper = mountForm(null);
    const [number, date] = wrapper.findAll("input:not([type='file'])");
    expect((number!.element as HTMLInputElement).value).toBe("");
    expect((date!.element as HTMLInputElement).value).toBe("");
    expect(wrapper.get(".file-picker").text()).toBe("Selecionar arquivo");
  });

  it("edição: campos preenchidos com o contrato e nome do arquivo atual", () => {
    const wrapper = mountForm(existing);
    const [number, date] = wrapper.findAll("input:not([type='file'])");
    expect((number!.element as HTMLInputElement).value).toBe("CT-0001");
    expect((date!.element as HTMLInputElement).value).toBe("2026-03-01");
    expect(wrapper.get(".file-picker").text()).toBe("contrato.pdf");
  });

  it("submit emite os valores digitados e o arquivo escolhido", async () => {
    const wrapper = mountForm(null);
    const [number, date] = wrapper.findAll("input:not([type='file'])");
    await number!.setValue("CT-0099");
    await date!.setValue("2026-05-20");
    const file = new File(["pdf"], "novo.pdf", { type: "application/pdf" });
    await chooseFile(wrapper, file);
    expect(wrapper.get(".file-picker").text()).toBe("novo.pdf");

    await wrapper.get("form").trigger("submit");

    expect(wrapper.emitted("submit")).toEqual([[{ contractNumber: "CT-0099", executedAt: "2026-05-20", file }]]);
  });

  it("submit sem arquivo novo envia file nulo", async () => {
    const wrapper = mountForm(existing);
    await wrapper.get("form").trigger("submit");
    expect(wrapper.emitted("submit")).toEqual([[{ contractNumber: "CT-0001", executedAt: "2026-03-01", file: null }]]);
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

describe("EquipmentContractsList (container)", () => {
  afterEach(() => vi.unstubAllGlobals());

  const listStubs = {
    AppModal: { props: ["open", "title"], template: "<div v-if='open' class='modal'><h2>{{ title }}</h2><slot /></div>" },
    RequirementWaiverBanner: true,
    Table: { template: "<div><slot /></div>" },
    TableHeader: { template: "<div><slot /></div>" },
    TableBody: { template: "<div><slot /></div>" },
    TableRow: { template: "<div><slot /></div>" },
    TableHead: { template: "<div><slot /></div>" },
    TableCell: { template: "<div><slot /></div>" },
  };

  it("cria o contrato e envia o arquivo escolhido para o endpoint do contrato criado", async () => {
    const post = vi.fn().mockResolvedValue({ ...existing, id: "ct-new" });
    const request = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("useApi", () => ({ post, patch: vi.fn(), delete: vi.fn(), request }));
    const wrapper = mount(EquipmentContractsList, {
      props: { equipmentId: "eq-1", contracts: [], editable: true },
      global: { stubs: listStubs },
    });

    await wrapper.get("[data-testid='add-contract']").trigger("click");
    expect(wrapper.get(".modal h2").text()).toBe("Novo contrato");
    const [number] = wrapper.findAll(".modal input:not([type='file'])");
    await number!.setValue("CT-0099");
    const file = new File(["pdf"], "novo.pdf");
    await chooseFile(wrapper, file);
    await wrapper.get(".modal form").trigger("submit");
    await flushPromises();

    expect(post).toHaveBeenCalledWith("/equipments/eq-1/contracts", { contractNumber: "CT-0099", executedAt: null });
    expect(request).toHaveBeenCalledTimes(1);
    const [url, options] = request.mock.calls[0]!;
    expect(url).toBe("/equipments/eq-1/contracts/ct-new/file");
    expect(options.method).toBe("PUT");
    expect(((options.body as FormData).get("file") as File).name).toBe("novo.pdf");
    expect(wrapper.emitted("changed")).toHaveLength(1);
    expect(wrapper.find(".modal").exists()).toBe(false);
  });

  it("edita via PATCH sem upload quando nenhum arquivo novo foi escolhido", async () => {
    const patch = vi.fn().mockResolvedValue(existing);
    const request = vi.fn();
    vi.stubGlobal("useApi", () => ({ post: vi.fn(), patch, delete: vi.fn(), request }));
    const wrapper = mount(EquipmentContractsList, {
      props: { equipmentId: "eq-1", contracts: [existing], editable: true },
      global: { stubs: listStubs },
    });

    await wrapper.findAll("button").find((item) => item.text().includes("Editar"))!.trigger("click");
    expect(wrapper.get(".modal h2").text()).toBe("Editar contrato");
    await wrapper.get(".modal form").trigger("submit");
    await flushPromises();

    expect(patch).toHaveBeenCalledWith("/equipments/eq-1/contracts/ct-1", { contractNumber: "CT-0001", executedAt: "2026-03-01" });
    expect(request).not.toHaveBeenCalled();
    expect(wrapper.emitted("changed")).toHaveLength(1);
  });

  it("exclui via DELETE e mostra o erro da API na seção quando falha", async () => {
    const del = vi.fn().mockRejectedValue(new Error("Contrato vinculado"));
    vi.stubGlobal("useApi", () => ({ post: vi.fn(), patch: vi.fn(), delete: del, request: vi.fn() }));
    const wrapper = mount(EquipmentContractsList, {
      props: { equipmentId: "eq-1", contracts: [existing], editable: true },
      global: { stubs: listStubs },
    });

    await wrapper.findAll("button").find((item) => item.text().includes("Excluir"))!.trigger("click");
    await flushPromises();

    expect(del).toHaveBeenCalledWith("/equipments/eq-1/contracts/ct-1");
    expect(wrapper.get(".list-notice").text()).toBe("Contrato vinculado");
    expect(wrapper.emitted("changed")).toBeUndefined();
  });
});
