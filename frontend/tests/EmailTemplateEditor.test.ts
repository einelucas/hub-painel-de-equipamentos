import { mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import EmailTemplateEditor from "~/components/admin/EmailTemplateEditor.vue";
import EmailTemplatePreview from "~/components/admin/EmailTemplatePreview.vue";
import EmailTestPanel from "~/components/admin/EmailTestPanel.vue";
import type { EmailTemplateDraft } from "~/types/notifications";

const DRAFT: EmailTemplateDraft = {
  subject: "Kickoff: {equipamento}",
  title: "Kickoff",
  intro: "Introdução",
  body: "Corpo do e-mail",
  buttonLabel: "Abrir equipamento",
  footer: "Rodapé institucional",
  customHtml: null,
  useCustomHtml: false,
  showDetails: true,
  showAlert: true,
  showButton: true,
  showFooter: true,
};

afterEach(() => vi.unstubAllGlobals());

describe("EmailTemplateEditor", () => {
  it("emite o modelo completo ao editar um campo", async () => {
    const wrapper = mount(EmailTemplateEditor, { props: { modelValue: { ...DRAFT } } });
    const title = wrapper.get('input[maxlength="160"]');

    await title.trigger("focus");
    await title.setValue("Novo título");

    const emitted = wrapper.emitted("update:modelValue") as EmailTemplateDraft[][];
    expect(emitted.at(-1)?.[0]?.title).toBe("Novo título");
    expect(emitted.at(-1)?.[0]?.body).toBe("Corpo do e-mail");
  });

  it("insere variável no último campo em foco", async () => {
    const wrapper = mount(EmailTemplateEditor, { props: { modelValue: { ...DRAFT } } });
    const body = wrapper.get("textarea[rows='5']");

    await body.trigger("focus");
    await wrapper.findAll(".tpl-variable-chip").at(1)!.trigger("click");

    const emitted = wrapper.emitted("update:modelValue") as EmailTemplateDraft[][];
    expect(emitted.at(-1)?.[0]?.body).toBe("Corpo do e-mail{tag}");
  });

  it("ativa o modo avançado e expõe o textarea de HTML", async () => {
    const wrapper = mount(EmailTemplateEditor, { props: { modelValue: { ...DRAFT } } });

    await wrapper.get(".tpl-advanced-toggle").trigger("click");
    const emitted = wrapper.emitted("update:modelValue") as EmailTemplateDraft[][];
    await wrapper.setProps({ modelValue: emitted[0]?.[0] });
    await wrapper.findAll(".tpl-editor-tabs button").at(1)!.trigger("click");

    expect(emitted[0]?.[0]).toMatchObject({ useCustomHtml: true });
    expect(wrapper.find(".tpl-html-editor").exists()).toBe(true);
    expect(wrapper.text()).toContain("removidos pelo backend");
  });

  it("insere variável no HTML avançado, não no corpo visual", async () => {
    const wrapper = mount(EmailTemplateEditor, { props: { modelValue: { ...DRAFT } } });
    await wrapper.setProps({
      modelValue: { ...DRAFT, useCustomHtml: true, customHtml: "<div></div>" },
    });

    await wrapper.findAll(".tpl-editor-tabs button").at(1)!.trigger("click");
    await wrapper.get(".tpl-html-editor").trigger("focus");
    await wrapper.findAll(".tpl-variable-chip").at(1)!.trigger("click");

    const emitted = wrapper.emitted("update:modelValue") as EmailTemplateDraft[][];
    expect(emitted.at(-1)?.[0]?.customHtml).toBe("<div></div>{tag}");
    expect(emitted.at(-1)?.[0]?.body).toBe("Corpo do e-mail");
  });

  it("dispara salvar e restaurar padrão", async () => {
    const wrapper = mount(EmailTemplateEditor, { props: { modelValue: { ...DRAFT } } });

    await wrapper.get(".tpl-editor-actions .btn.primary").trigger("click");
    await wrapper.findAll(".tpl-editor-actions .btn").at(1)!.trigger("click");

    expect(wrapper.emitted("save")).toHaveLength(1);
    expect(wrapper.emitted("reset")).toHaveLength(1);
  });
});

describe("EmailTemplatePreview", () => {
  it("renderiza o HTML em iframe isolado e alterna desktop/celular", async () => {
    const wrapper = mount(EmailTemplatePreview, {
      props: {
        preview: { subject: "Assunto", html: "<p>Olá</p>", text: "Olá", sample: true },
      },
    });
    const frame = wrapper.get("iframe");

    expect(frame.attributes("sandbox")).toBe("");
    expect(frame.attributes("srcdoc")).toBe("<p>Olá</p>");
    expect(wrapper.text()).toContain("Dados fictícios");

    await wrapper.findAll(".tpl-device-toggle button").at(1)!.trigger("click");
    expect(wrapper.get(".tpl-preview-stage").classes()).toContain("mobile");
  });
});

describe("EmailTestPanel", () => {
  const settings = {
    mode: "sandbox" as const,
    testInbox: "qa@example.test",
    providers: [
      { id: "graph" as const, name: "Microsoft Graph", configured: false },
      { id: "resend" as const, name: "Resend", configured: true },
    ],
  };

  it("no sandbox mantém a prévia com dados reais e envia pelo provedor", async () => {
    const wrapper = mount(EmailTestPanel, {
      props: {
        settings,
        equipmentOptions: [{ id: "eq-1", name: "Equipamento real" }],
        equipmentId: "eq-1",
        useSample: false,
      },
    });
    const checkbox = wrapper.get('input[type="checkbox"]');

    expect((checkbox.element as HTMLInputElement).checked).toBe(false);
    expect((checkbox.element as HTMLInputElement).disabled).toBe(false);
    expect(wrapper.text()).toContain("Equipamento real");
    expect(wrapper.text()).toContain("sempre fictício");

    await wrapper.get(".tpl-test .btn.primary").trigger("click");
    expect(wrapper.emitted("send")?.[0]?.[0]).toBe("resend");
  });

  it("permite escolher equipamento real quando não está em sandbox", async () => {
    const wrapper = mount(EmailTestPanel, {
      props: {
        settings: { ...settings, mode: "live" as const },
        equipmentOptions: [{ id: "eq-1", name: "Equipamento real" }],
        equipmentId: null,
        useSample: false,
      },
    });

    expect(wrapper.text()).toContain("Equipamento real");
    await wrapper.findAll("select").at(1)!.setValue("eq-1");
    expect(wrapper.emitted("update:equipmentId")?.[0]?.[0]).toBe("eq-1");
  });
});
