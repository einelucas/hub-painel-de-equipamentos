import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import RequirementWaiverBanner from "~/components/equipment/RequirementWaiverBanner.vue";
import type { RequirementGroup } from "~/types/equipment";

const group = {
  code: "NEGOTIATION_EQUALIZATION",
  label: "Equalização da negociação",
  status: "MISSING",
  waivable: true,
  fields: ["negotiation.equalized"],
  message: "Confirme a equalização da negociação.",
  waiver: null,
} satisfies RequirementGroup;

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("RequirementWaiverBanner", () => {
  it("usa VTextarea e envia a justificativa da dispensa", async () => {
    const post = vi.fn().mockResolvedValue({});
    vi.stubGlobal("useAuthStore", () => ({ can: () => true }));
    vi.stubGlobal("useApi", () => ({ post }));

    const wrapper = mount(RequirementWaiverBanner, {
      props: { equipmentId: "equipment-1", stage: 1, group },
      global: {
        stubs: {
          AppModal: {
            props: ["open", "title"],
            template: "<div v-if='open' class='modal-stub'><h2>{{ title }}</h2><slot /></div>",
          },
        },
      },
    });

    await wrapper.get("[data-testid='waive-NEGOTIATION_EQUALIZATION']").trigger("click");
    const justification = wrapper.get("[data-testid='waiver-justification']");
    expect(justification.classes()).toContain("v-textarea");

    await justification.get("textarea").setValue("Equalização não aplicável.");
    await wrapper.get(".waiver-form").trigger("submit");
    await flushPromises();

    expect(post).toHaveBeenCalledWith(
      "/equipments/equipment-1/requirement-waivers",
      {
        stage: 1,
        requirementGroupCode: "NEGOTIATION_EQUALIZATION",
        reasonCode: "OTHER",
        justification: "Equalização não aplicável.",
      },
    );
  });
});
