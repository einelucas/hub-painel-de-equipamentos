import { mount } from "@vue/test-utils";
import { nextTick } from "vue";
import { describe, expect, it } from "vitest";
import TipBadge from "~/components/ui/TipBadge.vue";

/**
 * O balão é preso à viewport (`position: fixed`), não ao badge: dentro de uma
 * tabela com `overflow` um balão `absolute` era recortado e só as últimas
 * linhas apareciam — a lista completa de work packages "sumia".
 */
function stubGeometry(element: HTMLElement, top: number): void {
  element.getBoundingClientRect = () =>
    ({
      top,
      bottom: top + 20,
      left: 100,
      right: 140,
      width: 40,
      height: 20,
      x: 100,
      y: top,
      toJSON: () => ({}),
    }) as DOMRect;
}

function stubSize(element: HTMLElement, width: number, height: number): void {
  Object.defineProperty(element, "offsetWidth", { configurable: true, value: width });
  Object.defineProperty(element, "offsetHeight", { configurable: true, value: height });
}

function mountTip(tip: string) {
  const wrapper = mount(TipBadge, { props: { label: "+7", tip } });
  return {
    wrapper,
    badge: wrapper.get(".tip-badge"),
    balloon: wrapper.get("[role='tooltip']"),
  };
}

describe("TipBadge", () => {
  it("guarda no balão o texto completo, com uma linha por item", async () => {
    const { badge, balloon } = mountTip("CAL004: Estruturas metálicas\nCAL005: WP sem descrição");

    expect(balloon.text()).toContain("CAL004: Estruturas metálicas");
    expect(balloon.text()).toContain("CAL005: WP sem descrição");
    expect(balloon.classes()).not.toContain("tip-badge-tip--open");

    await badge.trigger("mouseenter");
    expect(balloon.classes()).toContain("tip-badge-tip--open");

    await badge.trigger("mouseleave");
    expect(balloon.classes()).not.toContain("tip-badge-tip--open");
  });

  it("ancora o balão na viewport, acima do badge", async () => {
    const { badge, balloon } = mountTip("Estruturas metálicas");
    stubGeometry(badge.element as HTMLElement, 300);
    stubSize(balloon.element as HTMLElement, 200, 60);

    await badge.trigger("mouseenter");

    const style = balloon.attributes("style") ?? "";
    expect(style).toContain("left: 20px");
    expect(style).toContain(`bottom: ${window.innerHeight - 300 + 9}px`);
    expect(style).toContain("--tip-arrow: 100px");
    expect(balloon.classes()).not.toContain("tip-badge-tip--below");
  });

  it("abre abaixo quando a linha está no topo e não há espaço acima", async () => {
    const { badge, balloon } = mountTip("Estruturas metálicas");
    stubGeometry(badge.element as HTMLElement, 20);
    stubSize(balloon.element as HTMLElement, 200, 60);

    await badge.trigger("mouseenter");

    expect(balloon.classes()).toContain("tip-badge-tip--below");
    expect(balloon.attributes("style")).toContain("top: 49px");
  });

  it("acompanha a rolagem do contêiner que hospeda o badge", async () => {
    const { badge, balloon } = mountTip("Estruturas metálicas");
    stubGeometry(badge.element as HTMLElement, 300);
    stubSize(balloon.element as HTMLElement, 200, 60);
    await badge.trigger("mouseenter");

    stubGeometry(badge.element as HTMLElement, 120);
    window.dispatchEvent(new Event("scroll"));
    await nextTick();

    expect(balloon.attributes("style")).toContain(`bottom: ${window.innerHeight - 120 + 9}px`);
  });
});
