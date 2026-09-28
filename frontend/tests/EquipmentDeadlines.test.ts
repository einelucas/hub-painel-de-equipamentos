import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import EquipmentDeadlines from "~/components/equipment/EquipmentDeadlines.vue";
import type { EquipmentCalculated } from "~/types/equipment";

const empty: EquipmentCalculated = {
  maxLeadTimeDays: null,
  maxPreStartDays: null,
  maxFreightDays: null,
  deliveryDeadline: null,
  contractOrderDeadline: null,
  negotiationDeadline: null,
  negotiationDaysRemaining: null,
  negotiationStatus: null,
  workNeedDaysRemaining: null,
  workNeedStatus: null,
};

describe("EquipmentDeadlines", () => {
  it("dados completos: mostra números, datas formatadas e badges com rótulo/cor certos", () => {
    const calculated: EquipmentCalculated = {
      ...empty,
      maxLeadTimeDays: 155,
      maxPreStartDays: 120,
      maxFreightDays: 10,
      deliveryDeadline: "2027-06-29",
      contractOrderDeadline: "2027-01-15",
      negotiationDeadline: "2026-12-25",
      negotiationDaysRemaining: 93,
      negotiationStatus: "ON_TRACK",
      workNeedStatus: "SAFE",
    };
    const wrapper = mount(EquipmentDeadlines, { props: { calculated } });

    expect(wrapper.text()).toContain("155 dias");
    expect(wrapper.text()).toContain("120 dias");
    expect(wrapper.text()).toContain("10 dias");
    expect(wrapper.text()).toContain("29/06/2027");
    expect(wrapper.text()).toContain("15/01/2027");
    expect(wrapper.text()).toContain("25/12/2026");
    expect(wrapper.text()).toContain("93 dias restantes");

    const workNeed = wrapper.get("[data-testid='work-need-status-badge']");
    expect(workNeed.text()).toBe("Prazo seguro");
    expect(workNeed.classes()).toContain("negotiation-badge--ok");

    const negotiation = wrapper.get("[data-testid='negotiation-status-badge']");
    expect(negotiation.text()).toBe("No prazo");
    expect(negotiation.classes()).toContain("negotiation-badge--ok");
  });

  it("negociação atrasada: dias negativos viram 'dias em atraso' com o valor absoluto", () => {
    const calculated: EquipmentCalculated = {
      ...empty,
      negotiationDeadline: "2026-01-01",
      negotiationDaysRemaining: -7,
      negotiationStatus: "OVERDUE",
    };
    const wrapper = mount(EquipmentDeadlines, { props: { calculated } });

    expect(wrapper.text()).toContain("7 dias em atraso");
    expect(wrapper.text()).not.toContain("-7");
    const negotiation = wrapper.get("[data-testid='negotiation-status-badge']");
    expect(negotiation.text()).toBe("Atrasado");
    expect(negotiation.classes()).toContain("negotiation-badge--danger");
  });

  it("dados parciais: campos preenchidos e ausentes convivem sem quebrar", () => {
    const calculated: EquipmentCalculated = {
      ...empty,
      maxLeadTimeDays: 45,
      deliveryDeadline: "2027-03-10",
      workNeedStatus: "LT_30_DAYS",
    };
    const wrapper = mount(EquipmentDeadlines, { props: { calculated } });

    expect(wrapper.text()).toContain("45 dias");
    expect(wrapper.text()).toContain("10/03/2027");
    expect(wrapper.get("[data-testid='work-need-status-badge']").text()).toBe("< 30 dias");
    // negociação sem dados: sem parêntese de dias, badge neutro
    expect(wrapper.text()).not.toContain("dias restantes");
    expect(wrapper.text()).not.toContain("dias em atraso");
    expect(wrapper.get("[data-testid='negotiation-status-badge']").text()).toBe("—");
  });

  it("todos os valores ausentes: mostra travessão em cada campo e badges neutros", () => {
    const wrapper = mount(EquipmentDeadlines, { props: { calculated: empty } });

    const dashes = wrapper.findAll(".detail-field strong").map((node) => node.text());
    expect(dashes.every((text) => text.includes("—"))).toBe(true);

    const workNeed = wrapper.get("[data-testid='work-need-status-badge']");
    expect(workNeed.text()).toBe("—");
    expect(workNeed.classes()).toContain("negotiation-badge--neutral");

    const negotiation = wrapper.get("[data-testid='negotiation-status-badge']");
    expect(negotiation.text()).toBe("—");
    expect(negotiation.classes()).toContain("negotiation-badge--neutral");
  });

  it("mostra a nota de que os prazos são derivados dos componentes", () => {
    const wrapper = mount(EquipmentDeadlines, { props: { calculated: empty } });
    expect(wrapper.text()).toContain("Derivado dos componentes (FUN-001)");
  });
});
