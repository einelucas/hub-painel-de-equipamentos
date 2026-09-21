import { describe, expect, it } from "vitest";
import type { EngineeringRow } from "~/types/equipment";
import { NO_RESPONSIBLE_KEY, groupByResponsible } from "~/utils/engineering";

function row(id: string, responsible: { id: string; name: string } | null): EngineeringRow {
  return {
    equipmentId: id,
    equipmentName: `Equipamento ${id}`,
    unit: { id: "unit-1", code: "LEM", name: "Luís Eduardo Magalhães" },
    projectContext: { id: "ctx-1", code: "C2", name: "Caldeira 2" },
    currentStage: 0,
    currentStageName: "Nova demanda",
    nextStage: 1,
    nextStageName: "Negociação",
    pending: [],
    discipline: null,
    area: null,
    workPackages: [],
    responsibleUser: responsible ? { ...responsible, email: `${responsible.id}@inpasa.com.br` } : null,
    startupAt: null,
    criticality: null,
    componentsCount: 0,
  };
}

describe("groupByResponsible (GAP-011)", () => {
  it("agrupa equipamentos pelo responsável real, não por texto fixo", () => {
    const ana = { id: "u-ana", name: "Ana Carolina" };
    const uilson = { id: "u-uilson", name: "Uilson" };
    const rows = [row("A", ana), row("B", ana), row("C", uilson)];

    const groups = groupByResponsible(rows);

    expect(groups.map((g) => g.label)).toEqual(["Ana Carolina", "Uilson"]);
    expect(groups[0]!.rows.map((r) => r.equipmentId)).toEqual(["A", "B"]);
    expect(groups[1]!.rows.map((r) => r.equipmentId)).toEqual(["C"]);
  });

  it("agrupa em ordem alfabética pelo nome do responsável", () => {
    const groups = groupByResponsible([
      row("A", { id: "u-2", name: "Samuel" }),
      row("B", { id: "u-1", name: "Ediel" }),
    ]);
    expect(groups.map((g) => g.label)).toEqual(["Ediel", "Samuel"]);
  });

  it("equipamento sem responsável cai em 'Sem responsável', sempre por último", () => {
    const groups = groupByResponsible([
      row("A", null),
      row("B", { id: "u-1", name: "Ediel" }),
    ]);
    expect(groups.map((g) => g.label)).toEqual(["Ediel", "Sem responsável"]);
    expect(groups.find((g) => g.key === NO_RESPONSIBLE_KEY)?.rows.map((r) => r.equipmentId)).toEqual([
      "A",
    ]);
  });

  it("reagrupa automaticamente quando o responsável de uma linha muda (nova chamada com dados atualizados)", () => {
    const before = groupByResponsible([row("A", { id: "u-1", name: "Ediel" })]);
    expect(before.map((g) => g.label)).toEqual(["Ediel"]);

    const after = groupByResponsible([row("A", { id: "u-2", name: "Uilson" })]);
    expect(after.map((g) => g.label)).toEqual(["Uilson"]);
  });

  it("lista vazia não gera grupos", () => {
    expect(groupByResponsible([])).toEqual([]);
  });
});
