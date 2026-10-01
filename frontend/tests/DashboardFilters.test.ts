import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import DashboardFilters from "~/components/dashboard/DashboardFilters.vue";
import { useDashboardFilters } from "~/composables/useDashboardFilters";
import type { CatalogItem } from "~/types/equipment";
import { EQUIPMENT_STAGES } from "~/utils/stages";

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
  areaDisabled = false,
) {
  const wrapper = mount(DashboardFilters, {
    props: {
      areas,
      disciplines,
      areaDisabled,
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
  it("mostra Área, Fase e Disciplina, nessa ordem, com a opção 'Todas' e os catálogos recebidos", () => {
    const wrapper = mountFilters();
    expect(wrapper.findAll(".field > span").map((item) => item.text())).toEqual(["Área", "Fase", "Disciplina"]);
    expect(wrapper.get("[data-testid='dashboard-filter-area']").findAll("option").map((item) => item.text())).toEqual([
      "Todas as áreas",
      "Caldeira",
      "Drenagem",
    ]);
    expect(
      wrapper.get("[data-testid='dashboard-filter-discipline']").findAll("option").map((item) => item.text()),
    ).toEqual(["Todas as disciplinas", "Metal Mec.", "E&I"]);
  });

  it("a Fase usa o catálogo de etapas do workflow (0 a 8)", () => {
    const options = mountFilters().get("[data-testid='dashboard-filter-stage']").findAll("option");
    expect(options[0]!.text()).toBe("Todas as fases");
    expect(options.slice(1).map((item) => item.text())).toEqual(
      EQUIPMENT_STAGES.map((name, index) => `${index} · ${name}`),
    );
  });

  it("selecionar valores atualiza os modelos e emite change a cada alteração", async () => {
    const wrapper = mountFilters();
    await wrapper.get("[data-testid='dashboard-filter-area']").setValue("a-1");
    await wrapper.get("[data-testid='dashboard-filter-stage']").setValue("4");
    await wrapper.get("[data-testid='dashboard-filter-discipline']").setValue("d-1");

    expect(wrapper.props()).toMatchObject({ areaId: "a-1", stage: 4, disciplineId: "d-1" });
    expect(wrapper.emitted("change")).toHaveLength(3);
  });

  it("voltar para 'Todas' limpa só aquele filtro", async () => {
    const wrapper = mountFilters({ areaId: "a-1", stage: 0, disciplineId: "d-2" });
    await wrapper.get("[data-testid='dashboard-filter-stage']").setValue("");
    expect(wrapper.props()).toMatchObject({ areaId: "a-1", stage: null, disciplineId: "d-2" });
  });

  it("fase 0 (Nova demanda) conta como filtro ativo", () => {
    const wrapper = mountFilters({ stage: 0 });
    expect((wrapper.get("[data-testid='dashboard-filter-stage']").element as HTMLSelectElement).value).toBe("0");
    expect(wrapper.find("[data-testid='dashboard-filters-clear']").exists()).toBe(true);
  });

  it("'Limpar filtros' só aparece com algum filtro ativo e emite clear", async () => {
    expect(mountFilters().find("[data-testid='dashboard-filters-clear']").exists()).toBe(false);

    const wrapper = mountFilters({ disciplineId: "d-1" });
    await wrapper.get("[data-testid='dashboard-filters-clear']").trigger("click");
    expect(wrapper.emitted("clear")).toHaveLength(1);
  });

  it("Área fica desabilitada sem unidade selecionada", () => {
    const area = mountFilters({}, true).get("[data-testid='dashboard-filter-area']");
    expect(area.attributes("disabled")).toBeDefined();
    expect(area.attributes("title")).toBe("Selecione uma unidade para filtrar por área");
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
    expect(apiQuery.value).toEqual({ area_id: "a-1", stage: "0" });

    filters.disciplineId = "d-1";
    expect(apiQuery.value).toEqual({ area_id: "a-1", discipline_id: "d-1", stage: "0" });
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
