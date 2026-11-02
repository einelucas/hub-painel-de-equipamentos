import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import { VCheckbox, VChip, VPagination, VProgressCircular } from "vuetify/components";
import AppPagination from "~/components/ui/AppPagination.vue";
import Badge from "~/components/ui/Badge.vue";
import Checkbox from "~/components/ui/Checkbox.vue";
import LoadingSpinner from "~/components/ui/LoadingSpinner.vue";

describe("wrappers de UI do Hub com Vuetify", () => {
  it("Checkbox preserva v-model e estados nativos", async () => {
    const wrapper = mount(Checkbox, {
      props: { modelValue: false, indeterminate: true },
    });
    const checkbox = wrapper.findComponent(VCheckbox);

    expect(checkbox.props("density")).toBe("compact");
    expect(checkbox.props("hideDetails")).toBe(true);
    expect(checkbox.props("indeterminate")).toBe(true);
    checkbox.vm.$emit("update:modelValue", true);
    await wrapper.vm.$nextTick();

    expect(wrapper.emitted("update:modelValue")).toEqual([[true]]);
  });

  it.each([
    ["default", "primary", "tonal"],
    ["secondary", "secondary", "flat"],
    ["success", "success", "tonal"],
    ["destructive", "error", "tonal"],
    ["warning", "warning", "tonal"],
    ["outline", "secondary", "outlined"],
  ] as const)("Badge %s mantém cor e variante sem comportamento interativo", (variant, color, chipVariant) => {
    const wrapper = mount(Badge, {
      props: { variant },
      slots: { default: "Status" },
    });
    const chip = wrapper.findComponent(VChip);

    expect(chip.props("color")).toBe(color);
    expect(chip.props("variant")).toBe(chipVariant);
    expect(chip.props("link")).toBeFalsy();
    expect(wrapper.text()).toContain("Status");
  });

  it("AppPagination mantém página 1-based e emite uma única mudança válida", () => {
    const wrapper = mount(AppPagination, {
      props: { page: 2, totalPages: 5 },
    });
    const pagination = wrapper.findComponent(VPagination);

    expect(pagination.props("modelValue")).toBe(2);
    expect(pagination.props("length")).toBe(5);
    pagination.vm.$emit("update:modelValue", 3);
    pagination.vm.$emit("update:modelValue", 2);

    expect(wrapper.emitted("change")).toEqual([[3]]);
  });

  it("AppPagination respeita disabled e o estado sem páginas", async () => {
    const disabled = mount(AppPagination, {
      props: { page: 1, totalPages: 2, disabled: true },
    });
    disabled.findComponent(VPagination).vm.$emit("update:modelValue", 2);
    expect(disabled.emitted("change")).toBeUndefined();

    await disabled.setProps({ totalPages: 0, disabled: false });
    expect(disabled.findComponent(VPagination).exists()).toBe(false);
    expect(disabled.get("nav").attributes("aria-label")).toBe("Paginação de resultados");
  });

  it("LoadingSpinner usa progresso indeterminado, tamanhos e nome acessível", () => {
    const small = mount(LoadingSpinner, {
      props: { size: "sm", label: "Carregando catálogo..." },
    });
    const progress = small.findComponent(VProgressCircular);

    expect(progress.props("indeterminate")).toBe(true);
    expect(progress.props("size")).toBe(14);
    expect(progress.props("width")).toBe(2);
    expect(small.attributes("role")).toBe("status");
    expect(small.attributes("aria-label")).toBe("Carregando catálogo...");
  });
});
