import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import ComponentForm from "~/components/equipment/ComponentForm.vue";
import type { EquipmentComponent } from "~/types/equipment";

function component(overrides: Partial<EquipmentComponent> = {}): EquipmentComponent {
  return {
    id: "comp-1",
    equipmentId: "eq-1",
    name: "Motor auxiliar",
    tag: null,
    startupAt: "2027-06-05",
    sector: "Caldeira",
    leadTimeDays: 70,
    preStartDays: 90,
    contractDeliveryAt: null,
    freightDays: 10,
    calculated: {
      deliveryDeadline: null,
      availableForCollection: null,
      contractOrderDeadline: null,
      negotiationDeadline: null,
      negotiationDaysRemaining: null,
      deliveryMarginDays: null,
    },
    createdAt: "2026-09-20T00:00:00",
    updatedAt: "2026-09-20T00:00:00",
    ...overrides,
  };
}

describe("ComponentForm (GAP-009: startup próprio do componente)", () => {
  it("carrega o startup do componente ao editar, sem herdar de Equipment.startupAt", () => {
    const post = vi.fn();
    const patch = vi.fn().mockResolvedValue({});
    vi.stubGlobal("useApi", () => ({ get: vi.fn(), post, patch, delete: vi.fn() }));

    const wrapper = mount(ComponentForm, {
      props: { equipmentId: "eq-1", component: component() },
    });

    const startupInput = wrapper.get("input[type='date']");
    expect((startupInput.element as HTMLInputElement).value).toBe("2027-06-05");
  });

  it("envia startupAt no payload ao criar um componente novo", async () => {
    const post = vi.fn().mockResolvedValue(component());
    vi.stubGlobal("useApi", () => ({ get: vi.fn(), post, patch: vi.fn(), delete: vi.fn() }));

    const wrapper = mount(ComponentForm, { props: { equipmentId: "eq-1", component: null } });
    await wrapper.get("input[maxlength='200']").setValue("Bomba nova");
    await wrapper.get("input[type='date']").setValue("2027-08-10");
    await wrapper.get("form").trigger("submit");

    expect(post).toHaveBeenCalledWith(
      "/equipments/eq-1/components",
      expect.objectContaining({ startupAt: "2027-08-10" }),
    );
  });

  it("envia startupAt=null quando o campo é deixado em branco", async () => {
    const post = vi.fn().mockResolvedValue(component());
    vi.stubGlobal("useApi", () => ({ get: vi.fn(), post, patch: vi.fn(), delete: vi.fn() }));

    const wrapper = mount(ComponentForm, { props: { equipmentId: "eq-1", component: null } });
    await wrapper.get("input[maxlength='200']").setValue("Sem startup ainda");
    await wrapper.get("form").trigger("submit");

    expect(post).toHaveBeenCalledWith("/equipments/eq-1/components", expect.objectContaining({ startupAt: null }));
  });
});
