import { DOMWrapper, flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import { afterEach, describe, expect, it } from "vitest";
import { h, nextTick } from "vue";
import { VDialog } from "vuetify/components";
import AppModal from "~/components/ui/AppModal.vue";

let wrapper: VueWrapper | null = null;

function mountModal(props: Record<string, unknown> = {}) {
  wrapper = mount(AppModal, {
    attachTo: document.body,
    props: { open: true, title: "Editar registro", ...props },
    slots: {
      default: () => h("input", { "data-testid": "first-field" }),
      actions: () => [
        h("button", { type: "button", "data-testid": "cancel" }, "Cancelar"),
        h("button", { type: "submit", "data-testid": "save" }, "Salvar"),
      ],
    },
  });
  return wrapper;
}

function rendered(selector: string): DOMWrapper<Element> {
  const element = document.body.querySelector(selector);
  if (!element) throw new Error(`Elemento não renderizado: ${selector}`);
  return new DOMWrapper(element);
}

afterEach(async () => {
  wrapper?.unmount();
  wrapper = null;
  await nextTick();
  await flushPromises();
});

describe("AppModal com VDialog nativo", () => {
  it("renderiza o conteúdo e as ações em VDialog e VCard", async () => {
    const modal = mountModal();
    await flushPromises();

    expect(modal.findComponent(VDialog).exists()).toBe(true);
    expect(modal.findComponent(VDialog).props("modelValue")).toBe(true);
    expect(rendered(".modal-card h2").text()).toBe("Editar registro");
    expect(rendered(".modal-body [data-testid='first-field']").exists()).toBe(true);
    expect(rendered(".modal-actions [data-testid='save']").text()).toBe("Salvar");
  });

  it("o botão nativo de fechar emite close", async () => {
    const modal = mountModal();
    await flushPromises();

    await rendered(".modal-close").trigger("click");
    expect(modal.emitted("close")).toHaveLength(1);
  });

  it("preserva o diálogo aberto durante o salvamento", async () => {
    const modal = mountModal({ busy: true });
    await flushPromises();

    expect(modal.findComponent(VDialog).props("persistent")).toBe(true);
    expect(rendered(".modal-close").attributes("disabled")).toBeDefined();
    await rendered(".modal-close").trigger("click");
    expect(modal.emitted("close")).toBeUndefined();
  });

  it("desmonta o diálogo ao receber open=false", async () => {
    const modal = mountModal();
    await flushPromises();

    await modal.setProps({ open: false });
    await flushPromises();
    expect(modal.findComponent(VDialog).exists()).toBe(false);
  });

  it("usa largura wide e preserva o corpo de altura contida quando solicitado", async () => {
    const modal = mountModal({ size: "wide", contained: true });
    await flushPromises();
    expect(modal.findComponent(VDialog).props("maxWidth")).toBe(1040);
    expect(rendered(".modal-card").classes()).toContain("modal-card--contained");
  });

  it("usa persistent para impedir dismissal em fluxos restritos", async () => {
    const modal = mountModal({ dismissableMask: false });
    await flushPromises();
    expect(modal.findComponent(VDialog).props("persistent")).toBe(true);
  });
});
