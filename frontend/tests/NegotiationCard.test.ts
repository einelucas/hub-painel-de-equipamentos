import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import DashboardCard from "~/components/dashboard/DashboardCard.vue";
import NegotiationCard from "~/components/dashboard/NegotiationCard.vue";

describe("NegotiationCard", () => {
  it("exibe os números de negociação e o percentual concluído", () => {
    const wrapper = mount(NegotiationCard, {
      props: { negotiation: { open: 31, completed: 10, inNegotiation: 0 } },
      global: { components: { DashboardCard } },
    });

    expect(wrapper.text()).toContain("Negociação");
    expect(wrapper.text()).toContain("10");
    expect(wrapper.text()).toContain("41");
    expect(wrapper.text()).toContain("24,4%");
    expect(wrapper.text()).toContain("31");
  });

  it("não quebra quando não há negociações no recorte", () => {
    const wrapper = mount(NegotiationCard, {
      props: { negotiation: { open: 0, completed: 0, inNegotiation: 0 } },
      global: { components: { DashboardCard } },
    });
    expect(wrapper.text()).toContain("0,0%");
  });
});
