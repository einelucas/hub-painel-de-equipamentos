import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import EmailSettingsButton from "~/components/admin/EmailSettingsButton.vue";

function mountButton() {
  return mount(EmailSettingsButton, {
    global: {
      stubs: {
        NuxtLink: { props: ["to"], template: "<a :href='to'><slot /></a>" },
      },
    },
  });
}

describe("Configurar e-mails", () => {
  it("exibe o atalho para a central de e-mails ao lado da importação", () => {
    const link = mountButton().get("[data-testid='nav-email-settings']");
    expect(link.element.tagName).toBe("A");
    expect(link.attributes("href")).toBe("/administracao/notificacoes");
    expect(link.attributes("aria-label")).toBe("Configurar e-mails");
    expect(link.text()).toBe("Configurar e-mails");
  });
});
