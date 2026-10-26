import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import { afterEach, describe, expect, it } from "vitest";
import { h, nextTick } from "vue";
import AppModal from "~/components/ui/AppModal.vue";

let wrapper: VueWrapper | null = null;

function mountModal(props: Record<string, unknown> = {}) {
  wrapper = mount(AppModal, {
    attachTo: document.body,
    props: { open: true, title: "Editar registro", ...props },
    slots: {
      default: () =>
        h("label", { class: "field" }, [
          h("span", "Nome"),
          h("input", { "data-testid": "first-field" }),
        ]),
      actions: () => [
        h("button", { type: "button", "data-testid": "cancel" }, "Cancelar"),
        h("button", { type: "submit", "data-testid": "save" }, "Salvar"),
      ],
    },
  });
  return wrapper;
}

afterEach(() => {
  wrapper?.unmount();
  wrapper = null;
  document.body.style.overflow = "";
});

describe("AppModal", () => {
  it("abre como popup com título, foco no primeiro campo e rolagem bloqueada", async () => {
    const modal = mountModal();
    await flushPromises();

    expect(modal.get("[role='dialog']").attributes("aria-modal")).toBe("true");
    expect(modal.get(".modal-card h2").text()).toBe("Editar registro");
    expect(document.body.style.overflow).toBe("hidden");
    expect(document.activeElement).toBe(modal.get("[data-testid='first-field']").element);
  });

  it("fecha pelo X, pelo fundo e por Escape", async () => {
    const modal = mountModal();
    await flushPromises();

    await modal.get(".modal-close").trigger("click");
    await modal.get(".modal-backdrop").trigger("mousedown");
    await modal.get(".modal-card").trigger("keydown", { key: "Escape" });

    expect(modal.emitted("close")).toHaveLength(3);
  });

  it("mantém o foco dentro do modal ao tabular", async () => {
    const modal = mountModal();
    await flushPromises();

    const save = modal.get("[data-testid='save']").element as HTMLElement;
    save.focus();
    await modal.get(".modal-card").trigger("keydown", { key: "Tab" });

    expect(document.activeElement).toBe(modal.get(".modal-close").element);
  });

  it("não fecha com Escape enquanto há um dropdown aberto dentro do modal", async () => {
    const modal = mountModal();
    await flushPromises();

    const input = modal.get("[data-testid='first-field']");
    input.element.setAttribute("aria-expanded", "true");
    await input.trigger("keydown", { key: "Escape" });

    expect(modal.emitted("close")).toBeUndefined();
  });

  it("não fecha pelo X, fundo ou Escape enquanto está ocupado", async () => {
    const modal = mountModal({ busy: true });
    await flushPromises();

    await modal.get(".modal-close").trigger("click");
    await modal.get(".modal-backdrop").trigger("mousedown");
    await modal.get(".modal-card").trigger("keydown", { key: "Escape" });

    expect(modal.emitted("close")).toBeUndefined();
  });

  it("libera a rolagem do body ao fechar", async () => {
    const modal = mountModal();
    await flushPromises();
    expect(document.body.style.overflow).toBe("hidden");

    await modal.setProps({ open: false });
    await nextTick();

    expect(document.body.style.overflow).toBe("");
  });
});
