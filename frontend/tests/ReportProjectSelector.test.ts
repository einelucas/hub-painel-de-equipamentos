import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import { nextTick } from "vue";
import { afterEach, describe, expect, it } from "vitest";
import { VCheckbox, VDialog } from "vuetify/components";
import ReportProjectSelector from "~/components/equipment/ReportProjectSelector.vue";
import type { CatalogItem } from "~/types/equipment";

const projects: CatalogItem[] = [
  { id: "ctx-1", name: "Caldeira 2", code: "C2", active: true },
  { id: "ctx-2", name: "Fase 2", code: "F2", active: true },
  { id: "ctx-3", name: "Obra inativa", active: false },
];

let wrapper: VueWrapper | null = null;

async function render(initialSelectedId = "") {
  wrapper = mount(ReportProjectSelector, {
    attachTo: document.body,
    props: {
      open: true,
      unitName: "Luis Eduardo Magalhães",
      projects,
      initialSelectedId,
    },
  });
  await flushPromises();
  return wrapper;
}

afterEach(async () => {
  wrapper?.unmount();
  wrapper = null;
  await nextTick();
  await flushPromises();
});

describe("ReportProjectSelector", () => {
  it("abre VDialog com seleção da obra filtrada e permite várias obras", async () => {
    const modal = await render("ctx-1");
    expect(modal.findComponent(VDialog).props("modelValue")).toBe(true);
    expect(document.body.textContent).toContain("Selecionar obras do relatório");
    expect(document.body.textContent).toContain("Luis Eduardo Magalhães");
    const checkboxes = modal.findAllComponents(VCheckbox);
    expect(checkboxes).toHaveLength(2);
    expect(checkboxes[0]!.props("modelValue")).toBe(true);
    expect(checkboxes[1]!.props("modelValue")).toBe(false);

    checkboxes[1]!.vm.$emit("update:modelValue", true);
    await nextTick();
    expect(document.body.querySelector("[data-testid='report-selected-count']")?.textContent)
      .toContain("2 de 2");
    const generate = document.body.querySelector<HTMLElement>(
      "[data-testid='report-project-generate']",
    );
    generate?.click();
    await nextTick();
    expect(modal.emitted("generate")?.[0]).toEqual([["ctx-1", "ctx-2"]]);
  });

  it("exige ao menos uma obra e oferece seleção de todas", async () => {
    const modal = await render();
    expect(
      document.body.querySelector<HTMLButtonElement>("[data-testid='report-project-generate']")
        ?.disabled,
    ).toBe(true);

    document.body.querySelector<HTMLButtonElement>("[data-testid='report-select-all']")?.click();
    await nextTick();
    expect(
      document.body.querySelector<HTMLButtonElement>("[data-testid='report-project-generate']")
        ?.disabled,
    ).toBe(false);
    expect(document.body.querySelector("[data-testid='report-selected-count']")?.textContent)
      .toContain("2 de 2");

    document.body.querySelector<HTMLButtonElement>("[data-testid='report-select-all']")?.click();
    await nextTick();
    expect(
      document.body.querySelector<HTMLButtonElement>("[data-testid='report-project-generate']")
        ?.disabled,
    ).toBe(true);
    expect(modal.emitted("generate")).toBeUndefined();
  });

  it("reinicia a seleção ao reabrir e aceita cancelamento do VDialog", async () => {
    const modal = await render("ctx-2");
    modal.findComponent(VDialog).vm.$emit("update:modelValue", false);
    expect(modal.emitted("close")).toHaveLength(1);
    await modal.setProps({ open: false });
    await modal.setProps({ open: true, initialSelectedId: "" });
    await flushPromises();
    expect(modal.findAllComponents(VCheckbox).every((checkbox) => !checkbox.props("modelValue")))
      .toBe(true);
  });
});
