import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import Table from "~/components/ui/Table.vue";
import TableBody from "~/components/ui/TableBody.vue";
import TableHeader from "~/components/ui/TableHeader.vue";

describe("Table loading", () => {
  it("exibe o progresso em toda a largura logo abaixo do cabeçalho", () => {
    const wrapper = mount(Table, {
      props: { loading: true },
      slots: {
        default: "<TableHeader :loading='true'><tr><th>Nome</th><th>Etapa</th></tr></TableHeader><TableBody :loading='true' />",
      },
      global: {
        components: { TableBody, TableHeader },
        stubs: {
          VProgressLinear: {
            inheritAttrs: false,
            template: "<div data-testid='table-progress' />",
          },
          VSkeletonLoader: {
            inheritAttrs: false,
            template: "<div data-testid='vuetify-table-skeleton' />",
          },
        },
      },
    });

    const progressCell = wrapper.get(".table-progress-cell");
    expect(progressCell.attributes("colspan")).toBe("100");
    expect(progressCell.find("[data-testid='table-progress']").exists()).toBe(true);
    expect(wrapper.find("[data-testid='vuetify-table-skeleton']").exists()).toBe(true);
    expect(wrapper.attributes("aria-busy")).toBe("true");
  });

  it("remove a barra quando o carregamento termina", () => {
    const wrapper = mount(Table, {
      props: { loading: false },
      slots: { default: "<TableHeader><tr><th>Nome</th></tr></TableHeader>" },
      global: { components: { TableHeader } },
    });

    expect(wrapper.find(".table-progress-row").exists()).toBe(false);
  });
});
