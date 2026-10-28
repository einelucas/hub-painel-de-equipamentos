import { mount } from "@vue/test-utils";
import { afterEach, describe, expect, it } from "vitest";
import ConfirmDialog from "~/components/ui/ConfirmDialog.vue";
import { useConfirm } from "~/composables/useConfirm";

afterEach(() => {
  useConfirm().cancel();
});

describe("ConfirmDialog", () => {
  it("abre com título, mensagem e detalhe, e confirma resolvendo true", async () => {
    const wrapper = mount(ConfirmDialog);
    const { confirm, accept } = useConfirm();

    const result = confirm({
      message: 'Deseja excluir "Elétrica"?',
      detail: "Esta ação não pode ser desfeita.",
    });
    await wrapper.vm.$nextTick();

    const dialog = wrapper.get("[role='alertdialog']");
    expect((wrapper.get(".confirm-backdrop").element as HTMLElement).style.zIndex).toBe("10000");
    expect(dialog.text()).toContain("Zona de risco");
    expect(dialog.text()).toContain('Deseja excluir "Elétrica"?');
    expect(dialog.text()).toContain("Esta ação não pode ser desfeita.");
    expect(dialog.text()).toContain("Cancelar");
    expect(dialog.text()).toContain("Excluir");

    accept();
    await expect(result).resolves.toBe(true);
    await wrapper.vm.$nextTick();
    expect(wrapper.find("[role='alertdialog']").exists()).toBe(false);
    wrapper.unmount();
  });

  it("cancela pelo botão Cancelar resolvendo false", async () => {
    const wrapper = mount(ConfirmDialog);
    const { confirm } = useConfirm();

    const result = confirm({ message: "Excluir registro?" });
    await wrapper.vm.$nextTick();
    await wrapper.get(".confirm-btn--cancel").trigger("click");

    await expect(result).resolves.toBe(false);
    wrapper.unmount();
  });

  it("fecha com Escape e com clique no fundo", async () => {
    const wrapper = mount(ConfirmDialog);
    const { confirm } = useConfirm();

    const first = confirm({ message: "Excluir A?" });
    await wrapper.vm.$nextTick();
    await wrapper.get("[role='alertdialog']").trigger("keydown", { key: "Escape" });
    await expect(first).resolves.toBe(false);

    const second = confirm({ message: "Excluir B?" });
    await wrapper.vm.$nextTick();
    await wrapper.get(".confirm-backdrop").trigger("mousedown");
    await expect(second).resolves.toBe(false);

    wrapper.unmount();
  });

  it("usa o tom primário para ações não destrutivas", async () => {
    const wrapper = mount(ConfirmDialog);
    const { confirm } = useConfirm();

    void confirm({
      message: "Desativar registro?",
      confirmLabel: "Desativar",
      tone: "primary",
    });
    await wrapper.vm.$nextTick();

    expect(wrapper.find(".confirm-btn--danger").exists()).toBe(false);
    expect(wrapper.get(".confirm-btn--primary").text()).toBe("Desativar");
    wrapper.unmount();
  });
});
