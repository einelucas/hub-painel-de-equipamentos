import { DOMWrapper, flushPromises, mount } from "@vue/test-utils";
import { afterEach, describe, expect, it } from "vitest";
import { VDialog } from "vuetify/components";
import ConfirmDialog from "~/components/ui/ConfirmDialog.vue";
import { useConfirm } from "~/composables/useConfirm";

function rendered(selector: string): DOMWrapper<Element> {
  const element = document.body.querySelector(selector);
  if (!element) throw new Error(`Elemento não renderizado: ${selector}`);
  return new DOMWrapper(element);
}

afterEach(() => {
  useConfirm().cancel();
});

describe("ConfirmDialog com Vuetify", () => {
  it("mostra a mensagem e confirma a ação por um VBtn nativo", async () => {
    const wrapper = mount(ConfirmDialog, { attachTo: document.body });
    const result = useConfirm().confirm({
      message: 'Deseja excluir "Elétrica"?',
      detail: "Esta ação não pode ser desfeita.",
    });
    await flushPromises();

    expect(wrapper.findComponent(VDialog).props("modelValue")).toBe(true);
    expect(rendered(".confirm-card").text()).toContain("Zona de risco");
    expect(rendered(".confirm-card").text()).toContain('Deseja excluir "Elétrica"?');
    expect(rendered(".confirm-card").text()).toContain("Esta ação não pode ser desfeita.");
    await rendered(".confirm-btn--danger").trigger("click");

    await expect(result).resolves.toBe(true);
    wrapper.unmount();
  });

  it("cancela pelo botão Cancelar", async () => {
    const wrapper = mount(ConfirmDialog, { attachTo: document.body });
    const result = useConfirm().confirm({ message: "Excluir registro?" });
    await flushPromises();
    await rendered(".confirm-btn--cancel").trigger("click");
    await expect(result).resolves.toBe(false);
    wrapper.unmount();
  });

  it("cancela quando o VDialog emite fechamento nativo", async () => {
    const wrapper = mount(ConfirmDialog, { attachTo: document.body });
    const result = useConfirm().confirm({ message: "Excluir A?" });
    await flushPromises();
    wrapper.findComponent(VDialog).vm.$emit("update:modelValue", false);
    await expect(result).resolves.toBe(false);
    wrapper.unmount();
  });

  it("usa a variante e a cor primária para ações não destrutivas", async () => {
    const wrapper = mount(ConfirmDialog, { attachTo: document.body });
    void useConfirm().confirm({
      message: "Desativar registro?",
      confirmLabel: "Desativar",
      tone: "primary",
    });
    await flushPromises();
    expect(rendered(".confirm-card").text()).toContain("Desativar");
    expect(rendered(".confirm-btn--primary").exists()).toBe(true);
    wrapper.unmount();
  });
});
