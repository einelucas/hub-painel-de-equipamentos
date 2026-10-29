import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import NewProjectButton from "~/components/project-creation/NewProjectButton.vue";

vi.stubGlobal("useAuthStore", () => ({
  can: (permission: string) => ["catalogs:manage", "equipments:write"].includes(permission),
}));
vi.stubGlobal("useModuleContextStore", () => ({ selectedUnit: "unit-test" }));

describe("atalho de nova obra", () => {
  it("possui geometria e rótulo coerentes com os demais atalhos da navbar", () => {
    const wrapper = mount(NewProjectButton, {
      global: { stubs: { NewProjectModal: true } },
    });
    const button = wrapper.get("[data-testid='nav-new-project']");
    expect(button.attributes("aria-label")).toBe("Nova obra");
    expect(button.attributes("title")).toBe("Nova obra");
    expect(button.classes()).toContain("v-btn--icon");
    expect(button.classes()).toContain("v-btn--variant-text");
  });
});
