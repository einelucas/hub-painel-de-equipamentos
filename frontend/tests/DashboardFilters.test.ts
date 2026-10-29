import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import DashboardFilters from "~/components/dashboard/DashboardFilters.vue";
import { useDashboardFilters } from "~/composables/useDashboardFilters";
import type { CatalogItem } from "~/types/equipment";
import { EQUIPMENT_STAGES } from "~/utils/stages";
import { chooseOption, isDisabled, menuOptions, openMenu, optionLabels, shownValue } from "./support/searchableSelect";

const areas: CatalogItem[] = [
  { id: "a-1", name: "Caldeira", active: true },
  { id: "a-2", name: "Drenagem", active: true },
];
const disciplines: CatalogItem[] = [
  { id: "d-1", name: "Metal Mec.", active: true },
  { id: "d-2", name: "E&I", active: true },
];

function mountFilters(
  models: { areaId?: string | null; disciplineId?: string | null; stage?: number | null } = {},
) {
  const wrapper = mount(DashboardFilters, {
    props: {
      areas,
      disciplines,
      areaId: models.areaId ?? null,
      disciplineId: models.disciplineId ?? null,
      stage: models.stage ?? null,
      "onUpdate:areaId": (value: string | null) => wrapper.setProps({ areaId: value }),
      "onUpdate:disciplineId": (value: string | null) => wrapper.setProps({ disciplineId: value }),
      "onUpdate:stage": (value: number | null) => wrapper.setProps({ stage: value }),
    },
  });
  return wrapper;
}

describe("DashboardFilters", () => {
  it("mostra Área, Fase e Disciplina, nessa ordem, com a opção 'Todas' e os catálogos recebidos", async () => {
    const wrapper = mountFilters();
    expect(wrapper.findAll(".v-field-label:not(.v-field-label--floating)").map((item) => item.text())).toEqual([
      "Área",
      "Fase",
      "Disciplina",
    ]);
    expect(wrapper.findAll(".field > span")).toHaveLength(0);
    expect(await optionLabels(wrapper, "dashboard-filter-area")).toEqual(["Todas as áreas", "Caldeira", "Drenagem"]);
    expect(await optionLabels(wrapper, "dashboard-filter-discipline")).toEqual([
      "Todas as disciplinas",
      "E&I",
      "Metal Mec.",
    ]);
  });

  it("a Fase usa o catálogo de etapas do workflow (0 a 8), na ordem do processo", async () => {
    const labels = await optionLabels(mountFilters(), "dashboard-filter-stage");
    expect(labels[0]).toBe("Todas as fases");
    expect(labels.slice(1)).toEqual(EQUIPMENT_STAGES.map((name, index) => `${index} · ${name}`));
  });

  it("selecionar valores atualiza os modelos e emite change a cada alteração", async () => {
    const wrapper = mountFilters();
    await chooseOption(wrapper, "dashboard-filter-area", "Caldeira");
    await chooseOption(wrapper, "dashboard-filter-stage", `4 · ${EQUIPMENT_STAGES[4]}`);
    await chooseOption(wrapper, "dashboard-filter-discipline", "Metal Mec.");

    expect(wrapper.props()).toMatchObject({ areaId: "a-1", stage: 4, disciplineId: "d-1" });
    expect(wrapper.emitted("change")).toHaveLength(3);
  });

  it("voltar para 'Todas' limpa só aquele filtro", async () => {
    const wrapper = mountFilters({ areaId: "a-1", stage: 0, disciplineId: "d-2" });
    await chooseOption(wrapper, "dashboard-filter-stage", "Todas as fases");
    expect(wrapper.props()).toMatchObject({ areaId: "a-1", stage: null, disciplineId: "d-2" });
  });

  it("fase 0 (Nova demanda) conta como filtro ativo", () => {
    const wrapper = mountFilters({ stage: 0 });
    expect(shownValue(wrapper, "dashboard-filter-stage")).toBe(`0 · ${EQUIPMENT_STAGES[0]}`);
    expect(wrapper.find("[data-testid='dashboard-filters-clear']").exists()).toBe(true);
  });

  it("'Limpar filtros' só aparece com algum filtro ativo e emite clear", async () => {
    expect(mountFilters().find("[data-testid='dashboard-filters-clear']").exists()).toBe(false);

    const wrapper = mountFilters({ disciplineId: "d-1" });
    await wrapper.get("[data-testid='dashboard-filters-clear']").trigger("click");
    expect(wrapper.emitted("clear")).toHaveLength(1);
  });

  it("Área (EAP global) fica habilitada mesmo sem unidade selecionada", () => {
    expect(isDisabled(mountFilters(), "dashboard-filter-area")).toBe(false);
  });

  it("Área é pesquisável e escolher a opção já selecionada não emite change", async () => {
    const wrapper = mountFilters({ areaId: "a-1" });
    const input = wrapper.get("input[role='combobox']");
    await openMenu(wrapper, "dashboard-filter-area");
    (input.element as HTMLInputElement).focus();
    await flushPromises();
    await input.setValue("dren");
    await flushPromises();
    await new Promise((r) => setTimeout(r, 50));
    expect(
      menuOptions(wrapper, "dashboard-filter-area").map((item) => item.find(".v-list-item-title").text()),
    ).toEqual(["Todas as áreas", "Drenagem"]);

    await chooseOption(wrapper, "dashboard-filter-area", "Drenagem");
    await chooseOption(wrapper, "dashboard-filter-area", "Drenagem");
    expect(wrapper.props("areaId")).toBe("a-2");
    expect(wrapper.emitted("change")).toHaveLength(1);
  });
});

describe("useDashboardFilters", () => {
  it("sem seleção não envia nenhum parâmetro à API", () => {
    const { apiQuery, hasActive } = useDashboardFilters();
    expect(apiQuery.value).toEqual({});
    expect(hasActive.value).toBe(false);
  });

  it("envia só os filtros selecionados, com os nomes do endpoint", () => {
    const { filters, apiQuery } = useDashboardFilters();
    filters.areaId = "a-1";
    filters.stage = 0;
    expect(apiQuery.value).toEqual({ eap_node_id: "a-1", stage: "0" });

    filters.disciplineId = "d-1";
    expect(apiQuery.value).toEqual({ eap_node_id: "a-1", discipline_id: "d-1", stage: "0" });
  });

  it("lê a URL (?area=&discipline=&stage=) e ignora fase inválida", () => {
    const { filters, readRouteQuery } = useDashboardFilters();
    readRouteQuery({ area: "a-1", discipline: "d-1", stage: "4" });
    expect({ ...filters }).toEqual({ areaId: "a-1", disciplineId: "d-1", stage: 4 });

    readRouteQuery({ stage: "9" });
    expect({ ...filters }).toEqual({ areaId: null, disciplineId: null, stage: null });

    readRouteQuery({ stage: "abc", area: "" });
    expect({ ...filters }).toEqual({ areaId: null, disciplineId: null, stage: null });
  });

  it("escreve na URL só os filtros ativos, preservando os outros parâmetros", () => {
    const { filters, writeRouteQuery } = useDashboardFilters();
    filters.stage = 2;
    const query: Record<string, string> = { unit: "u-1", area: "antiga", discipline: "antiga" };
    writeRouteQuery(query);
    expect(query).toEqual({ unit: "u-1", stage: "2" });
  });

  it("clear volta os três filtros para 'Todas'", () => {
    const { filters, clear, hasActive, apiQuery } = useDashboardFilters();
    Object.assign(filters, { areaId: "a-1", disciplineId: "d-1", stage: 3 });
    clear();
    expect(hasActive.value).toBe(false);
    expect(apiQuery.value).toEqual({});
  });
});
