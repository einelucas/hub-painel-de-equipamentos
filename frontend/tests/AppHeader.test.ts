import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import AppHeader from "~/components/AppHeader.vue";

/**
 * Regressão do shell corporativo: o header pertence ao Hub. O Painel não pode
 * acoplar buscas próprias nele nem desabilitar/remover seus controles.
 */
function mountHeader(role = "ADMIN") {
  vi.stubGlobal("useRouter", () => ({ back: vi.fn() }));
  vi.stubGlobal("useAuth", () => ({ store: { user: { name: "Dev", role } } }));
  return mount(AppHeader, {
    global: {
      stubs: {
        NuxtLink: { props: ["to"], template: "<a :href='to'><slot /></a>" },
        UserMenu: { template: "<div data-testid='user-menu' />" },
      },
    },
  });
}

describe("AppHeader (shell do Hub)", () => {
  it("mantém os controles corporativos previstos", () => {
    const wrapper = mountHeader();
    expect(wrapper.find("input[type='search']").exists()).toBe(true);
    expect(wrapper.find("[data-testid='user-menu']").exists()).toBe(true);
    expect(wrapper.text()).toContain("Voltar");
    expect(wrapper.text()).toContain("Registro de Atividades");
    // Sino e exportação continuam presentes como botões do shell.
    expect(wrapper.findAll("button").length).toBeGreaterThanOrEqual(3);
  });

  it("não desabilita nenhum controle do shell", () => {
    const wrapper = mountHeader();
    const search = wrapper.get("input[type='search']");
    expect(search.attributes("disabled")).toBeUndefined();
    const disabledButtons = wrapper
      .findAll("button")
      .filter((button) => button.attributes("disabled") !== undefined);
    expect(disabledButtons).toHaveLength(0);
  });

  it("não acopla busca do Painel ao campo do Hub", () => {
    const wrapper = mountHeader();
    const search = wrapper.get("input[type='search']");
    // Sem handler de input/change: a busca é responsabilidade do Hub.
    expect(search.attributes("onInput")).toBeUndefined();
    expect(search.attributes("onChange")).toBeUndefined();
    expect(wrapper.html()).not.toContain("/equipments");
    expect(wrapper.html()).not.toContain("equipamento");
  });

  it("esconde o Registro de Atividades de quem não é ADMIN", () => {
    expect(mountHeader("VIEWER").text()).not.toContain("Registro de Atividades");
  });
});
