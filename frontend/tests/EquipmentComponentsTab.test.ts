import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import EquipmentComponentsTab from "~/components/equipment/EquipmentComponentsTab.vue";
import type { EquipmentComponent } from "~/types/equipment";

/**
 * Reaproveita `ComponentForm` como está (não é o alvo do teste — já tem
 * teste próprio em ComponentForm.test.ts), então aqui ele é substituído por
 * um stub que expõe o que recebeu e permite disparar `saved`/`cancel`. O
 * mesmo vale para `AppModal` (Teleport) e para os componentes de tabela.
 */
const appModalStub = {
  props: ["open", "title"],
  template: "<div v-if=\"open\" class=\"modal-stub\"><p>{{ title }}</p><slot /></div>",
};
const componentFormStub = {
  props: ["equipmentId", "component"],
  emits: ["saved", "cancel"],
  template: `<div data-testid="stub-component-form">{{ component ? component.id : 'new' }}
    <button data-testid="stub-save" type="button" @click="$emit('saved', component ?? { id: 'created-id' })">save</button>
    <button data-testid="stub-cancel" type="button" @click="$emit('cancel')">cancel</button>
  </div>`,
};
const passthrough = { template: "<div><slot /></div>" };

function component(overrides: Partial<EquipmentComponent> = {}): EquipmentComponent {
  return {
    id: "comp-1",
    equipmentId: "eq-1",
    name: "Motor auxiliar",
    tag: "MOT-01",
    startupAt: "2027-06-05",
    sector: "Caldeira",
    leadTimeDays: 70,
    preStartDays: 90,
    contractDeliveryAt: "2027-04-01",
    freightDays: 10,
    calculated: {
      deliveryDeadline: "2027-05-01",
      availableForCollection: "2027-04-20",
      contractOrderDeadline: "2027-02-15",
      negotiationDeadline: "2027-01-10",
      negotiationDaysRemaining: 30,
      deliveryMarginDays: 5,
    },
    createdAt: "2026-09-20T00:00:00",
    updatedAt: "2026-09-20T00:00:00",
    ...overrides,
  };
}

function mountTab(items: EquipmentComponent[], canEdit = true) {
  const wrapper = mount(EquipmentComponentsTab, {
    props: { equipmentId: "eq-1", components: items, canEdit },
    global: {
      components: { ComponentForm: componentFormStub },
      stubs: {
        AppModal: appModalStub,
        Table: passthrough,
        TableHeader: passthrough,
        TableRow: passthrough,
        TableHead: passthrough,
        TableBody: passthrough,
        TableCell: passthrough,
      },
    },
  });
  return { wrapper };
}

describe("EquipmentComponentsTab", () => {
  it("estado vazio: mostra a mensagem e nenhuma tabela", () => {
    const { wrapper } = mountTab([]);
    expect(wrapper.text()).toContain("Nenhum componente cadastrado");
    expect(wrapper.find("[data-testid^='toggle-deadlines-']").exists()).toBe(false);
  });

  it("lista: mostra nome, tag, datas formatadas e campos com dias; ausentes viram travessão", () => {
    const partial = component({ id: "comp-2", tag: null, leadTimeDays: null, contractDeliveryAt: null });
    const { wrapper } = mountTab([component(), partial]);

    expect(wrapper.text()).toContain("Motor auxiliar");
    expect(wrapper.text()).toContain("MOT-01");
    expect(wrapper.text()).toContain("05/06/2027");
    expect(wrapper.text()).toContain("70 dias");
    expect(wrapper.text()).toContain("90 dias");
    expect(wrapper.text()).toContain("10 dias");
    // componente parcial: tag e lead time ausentes
    const cells = wrapper.text();
    expect(cells).toContain("—");
  });

  it("esconde 'Adicionar componente' e 'Editar' sem permissão de escrita", () => {
    const { wrapper } = mountTab([component()], false);
    expect(wrapper.text()).not.toContain("Adicionar componente");
    expect(wrapper.findAll("button").some((btn) => btn.text() === "Editar")).toBe(false);
  });

  it("Prazos calculados: expande uma linha por vez, sem desarrumar o texto do botão das demais", async () => {
    const { wrapper } = mountTab([component({ id: "comp-1" }), component({ id: "comp-2", name: "Bomba" })]);

    expect(wrapper.find("[data-testid='deadlines-comp-1']").exists()).toBe(false);
    expect(wrapper.find("[data-testid='deadlines-comp-2']").exists()).toBe(false);

    await wrapper.get("[data-testid='toggle-deadlines-comp-1']").trigger("click");
    expect(wrapper.find("[data-testid='deadlines-comp-1']").exists()).toBe(true);
    expect(wrapper.find("[data-testid='deadlines-comp-2']").exists()).toBe(false);
    expect(wrapper.get("[data-testid='toggle-deadlines-comp-1']").text()).toBe("Ocultar prazos");
    expect(wrapper.get("[data-testid='toggle-deadlines-comp-2']").text()).toBe("Prazos calculados");

    const deadlines1 = wrapper.get("[data-testid='deadlines-comp-1']").text();
    expect(deadlines1).toContain("01/05/2027");
    expect(deadlines1).toContain("20/04/2027");
    expect(deadlines1).toContain("15/02/2027");
    expect(deadlines1).toContain("10/01/2027");

    // abrir a outra linha troca qual está expandida (acordeão de 1 só) e
    // não deixa o botão da linha 1 com rótulo desatualizado
    await wrapper.get("[data-testid='toggle-deadlines-comp-2']").trigger("click");
    expect(wrapper.find("[data-testid='deadlines-comp-1']").exists()).toBe(false);
    expect(wrapper.find("[data-testid='deadlines-comp-2']").exists()).toBe(true);
    expect(wrapper.get("[data-testid='toggle-deadlines-comp-1']").text()).toBe("Prazos calculados");
    expect(wrapper.get("[data-testid='toggle-deadlines-comp-2']").text()).toBe("Ocultar prazos");

    // clicar de novo na mesma linha recolhe
    await wrapper.get("[data-testid='toggle-deadlines-comp-2']").trigger("click");
    expect(wrapper.find("[data-testid='deadlines-comp-2']").exists()).toBe(false);
  });

  it("Adicionar: abre o modal 'Novo componente' com o formulário vazio (sem componente)", async () => {
    const { wrapper } = mountTab([component()]);
    await wrapper.findAll("button").find((btn) => btn.text().includes("Adicionar componente"))!.trigger("click");

    expect(wrapper.get(".modal-stub p").text()).toBe("Novo componente");
    expect(wrapper.get("[data-testid='stub-component-form']").text()).toContain("new");
  });

  it("Editar: abre o modal com o registro correto do componente clicado", async () => {
    const { wrapper } = mountTab([component({ id: "comp-1", name: "Motor" }), component({ id: "comp-2", name: "Bomba" })]);
    const editButtons = wrapper.findAll("button").filter((btn) => btn.text() === "Editar");
    expect(editButtons).toHaveLength(2);

    await editButtons[1]!.trigger("click");

    expect(wrapper.get(".modal-stub p").text()).toBe("Editar componente");
    expect(wrapper.get("[data-testid='stub-component-form']").text()).toContain("comp-2");
  });

  it("Cancelar: fecha o modal sem emitir 'saved'", async () => {
    const { wrapper } = mountTab([component()]);
    await wrapper.findAll("button").find((btn) => btn.text().includes("Adicionar componente"))!.trigger("click");
    await wrapper.get("[data-testid='stub-cancel']").trigger("click");

    expect(wrapper.find(".modal-stub").exists()).toBe(false);
    expect(wrapper.emitted("saved")).toBeUndefined();
  });

  it("Salvar: fecha o modal e emite 'saved' para a página recarregar", async () => {
    const { wrapper } = mountTab([component()]);
    const editButtons = wrapper.findAll("button").filter((btn) => btn.text() === "Editar");
    await editButtons[0]!.trigger("click");
    await wrapper.get("[data-testid='stub-save']").trigger("click");

    expect(wrapper.find(".modal-stub").exists()).toBe(false);
    expect(wrapper.emitted("saved")).toHaveLength(1);
  });
});
