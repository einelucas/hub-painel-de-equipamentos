import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import NewProjectButton from "~/components/project-creation/NewProjectButton.vue";
import { useProjectCreation } from "~/composables/useProjectCreation";

vi.stubGlobal("useAuthStore", () => ({
  can: (permission: string) => ["catalogs:manage", "equipments:write"].includes(permission),
}));
vi.stubGlobal("useModuleContextStore", () => ({ selectedUnit: "unit-test" }));

describe("atalho de nova obra", () => {
  it("possui geometria e abre a instância compartilhada do wizard", async () => {
    const wrapper = mount(NewProjectButton, {
      global: { stubs: { NewProjectModal: true } },
    });
    const button = wrapper.get("[data-testid='nav-new-project']");
    expect(button.attributes("aria-label")).toBe("Nova obra");
    expect(button.attributes("title")).toBeUndefined();
    expect(button.classes()).toContain("v-btn--icon");
    expect(button.classes()).toContain("v-btn--variant-text");
    expect(button.get(".module-nav-tip").text()).toBe("Nova obra");
    await button.trigger("click");
    expect(useProjectCreation().open.value).toBe(true);
    expect(useProjectCreation().initialUnitId.value).toBe("unit-test");
    useProjectCreation().closeNewProject();
  });
});
