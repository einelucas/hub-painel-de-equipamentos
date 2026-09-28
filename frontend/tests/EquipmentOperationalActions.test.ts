import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import JustificationModal from "~/components/equipment/JustificationModal.vue";
import EquipmentOperationalActions from "~/components/equipment/EquipmentOperationalActions.vue";
import type { OperationalStatus } from "~/types/equipment";

/**
 * AppModal usa <Teleport to="body">, que complica a busca por elementos em
 * testes de montagem isolada. Como já é feito em EquipmentSuppliers.test.ts,
 * substituímos por uma div simples que ainda respeita `open` — preserva o
 * comportamento de mostrar/esconder sem a complexidade do Teleport.
 */
const appModalStub = {
  props: ["open", "title"],
  template: "<div v-if=\"open\" class=\"modal-stub\"><slot /></div>",
};

function mountActions(
  operationalStatus: OperationalStatus,
  overrides: Partial<{
    enterStandby: ReturnType<typeof vi.fn>;
    liftStandby: ReturnType<typeof vi.fn>;
    cancelEquipment: ReturnType<typeof vi.fn>;
    enterSanitation: ReturnType<typeof vi.fn>;
    endSanitation: ReturnType<typeof vi.fn>;
  }> = {},
) {
  const enterStandby = overrides.enterStandby ?? vi.fn().mockResolvedValue({});
  const liftStandby = overrides.liftStandby ?? vi.fn().mockResolvedValue({});
  const cancelEquipment = overrides.cancelEquipment ?? vi.fn().mockResolvedValue({});
  const enterSanitation = overrides.enterSanitation ?? vi.fn().mockResolvedValue({});
  const endSanitation = overrides.endSanitation ?? vi.fn().mockResolvedValue({});

  const wrapper = mount(EquipmentOperationalActions, {
    props: {
      operationalStatus,
      canOperate: true,
      busy: false,
      actionError: "",
      enterStandby,
      liftStandby,
      cancelEquipment,
      enterSanitation,
      endSanitation,
    },
    global: {
      components: { JustificationModal },
      stubs: { AppModal: appModalStub },
    },
  });
  return { wrapper, enterStandby, liftStandby, cancelEquipment, enterSanitation, endSanitation };
}

async function fillAndSubmit(wrapper: ReturnType<typeof mount>, text: string): Promise<void> {
  await wrapper.get("textarea").setValue(text);
  await wrapper.get("form").trigger("submit");
  await wrapper.vm.$nextTick();
}

describe("EquipmentOperationalActions", () => {
  it("esconde a seção inteira para quem não tem workflow:transition", () => {
    const wrapper = mount(EquipmentOperationalActions, {
      props: {
        operationalStatus: "ACTIVE",
        canOperate: false,
        busy: false,
        actionError: "",
        enterStandby: vi.fn(),
        liftStandby: vi.fn(),
        cancelEquipment: vi.fn(),
        enterSanitation: vi.fn(),
        endSanitation: vi.fn(),
      },
      global: { components: { JustificationModal }, stubs: { AppModal: appModalStub } },
    });
    expect(wrapper.find("[data-testid='standby-button']").exists()).toBe(false);
    expect(wrapper.html()).toBe("<!--v-if-->");
  });

  it("ACTIVE mostra Standby/Saneamento/Cancelar; outros estados não aparecem", () => {
    const { wrapper } = mountActions("ACTIVE");
    expect(wrapper.find("[data-testid='standby-button']").exists()).toBe(true);
    expect(wrapper.find("[data-testid='sanitation-button']").exists()).toBe(true);
    expect(wrapper.find("[data-testid='cancel-button']").exists()).toBe(true);
    expect(wrapper.find("[data-testid='lift-standby-button']").exists()).toBe(false);
    expect(wrapper.find("[data-testid='end-sanitation-button']").exists()).toBe(false);
  });

  it("STANDBY só mostra Remover Standby", () => {
    const { wrapper } = mountActions("STANDBY");
    expect(wrapper.find("[data-testid='standby-button']").exists()).toBe(false);
    expect(wrapper.find("[data-testid='lift-standby-button']").exists()).toBe(true);
  });

  it("IN_SANITATION só mostra Encerrar Saneamento", () => {
    const { wrapper } = mountActions("IN_SANITATION");
    expect(wrapper.find("[data-testid='end-sanitation-button']").exists()).toBe(true);
    expect(wrapper.find("[data-testid='standby-button']").exists()).toBe(false);
  });

  it("CANCELLED só mostra a nota de que o fluxo normal não pode ser retomado", () => {
    const { wrapper } = mountActions("CANCELLED");
    expect(wrapper.text().toLowerCase()).toContain("retom");
    expect(wrapper.find("[data-testid='standby-button']").exists()).toBe(false);
  });

  it("Standby: confirmar chama enterStandby com o texto e fecha o modal em sucesso", async () => {
    const { wrapper, enterStandby } = mountActions("ACTIVE");
    await wrapper.get("[data-testid='standby-button']").trigger("click");
    expect(wrapper.find(".modal-stub").exists()).toBe(true);

    await fillAndSubmit(wrapper, "Pausa temporária do fornecedor.");

    expect(enterStandby).toHaveBeenCalledWith("Pausa temporária do fornecedor.");
    expect(wrapper.find(".modal-stub").exists()).toBe(false);
  });

  it("Standby: se enterStandby falhar (retorno null), o modal permanece aberto", async () => {
    const { wrapper, enterStandby } = mountActions("ACTIVE", {
      enterStandby: vi.fn().mockResolvedValue(null),
    });
    await wrapper.get("[data-testid='standby-button']").trigger("click");
    await fillAndSubmit(wrapper, "Justificativa qualquer.");

    expect(enterStandby).toHaveBeenCalled();
    expect(wrapper.find(".modal-stub").exists()).toBe(true);
  });

  it("Standby: cancelar no modal fecha sem chamar enterStandby", async () => {
    const { wrapper, enterStandby } = mountActions("ACTIVE");
    await wrapper.get("[data-testid='standby-button']").trigger("click");
    await wrapper.get(".modal-stub form button[type='button']").trigger("click");

    expect(enterStandby).not.toHaveBeenCalled();
    expect(wrapper.find(".modal-stub").exists()).toBe(false);
  });

  it("Remover Standby: confirmar chama liftStandby e fecha em sucesso (retorno não-null)", async () => {
    const { wrapper, liftStandby } = mountActions("STANDBY");
    await wrapper.get("[data-testid='lift-standby-button']").trigger("click");
    await fillAndSubmit(wrapper, "");

    expect(liftStandby).toHaveBeenCalledWith("");
    expect(wrapper.find(".modal-stub").exists()).toBe(false);
  });

  it("Remover Standby: retorno null mantém o modal aberto", async () => {
    const { wrapper } = mountActions("STANDBY", { liftStandby: vi.fn().mockResolvedValue(null) });
    await wrapper.get("[data-testid='lift-standby-button']").trigger("click");
    await fillAndSubmit(wrapper, "");

    expect(wrapper.find(".modal-stub").exists()).toBe(true);
  });

  it("Cancelar equipamento: confirmar chama cancelEquipment e fecha em sucesso", async () => {
    const { wrapper, cancelEquipment } = mountActions("ACTIVE");
    await wrapper.get("[data-testid='cancel-button']").trigger("click");
    await fillAndSubmit(wrapper, "Projeto descontinuado.");

    expect(cancelEquipment).toHaveBeenCalledWith("Projeto descontinuado.");
    expect(wrapper.find(".modal-stub").exists()).toBe(false);
  });

  it("Colocar em Saneamento: confirmar chama enterSanitation e fecha em sucesso", async () => {
    const { wrapper, enterSanitation } = mountActions("ACTIVE");
    await wrapper.get("[data-testid='sanitation-button']").trigger("click");
    await fillAndSubmit(wrapper, "Equipamento fora de uso.");

    expect(enterSanitation).toHaveBeenCalledWith("Equipamento fora de uso.");
    expect(wrapper.find(".modal-stub").exists()).toBe(false);
  });

  it("Encerrar Saneamento: confirmar chama endSanitation e fecha em sucesso (retorno não-null)", async () => {
    const { wrapper, endSanitation } = mountActions("IN_SANITATION");
    await wrapper.get("[data-testid='end-sanitation-button']").trigger("click");
    await fillAndSubmit(wrapper, "");

    expect(endSanitation).toHaveBeenCalledWith("");
    expect(wrapper.find(".modal-stub").exists()).toBe(false);
  });

  it("Encerrar Saneamento: retorno null mantém o modal aberto", async () => {
    const { wrapper } = mountActions("IN_SANITATION", {
      endSanitation: vi.fn().mockResolvedValue(null),
    });
    await wrapper.get("[data-testid='end-sanitation-button']").trigger("click");
    await fillAndSubmit(wrapper, "");

    expect(wrapper.find(".modal-stub").exists()).toBe(true);
  });
});
