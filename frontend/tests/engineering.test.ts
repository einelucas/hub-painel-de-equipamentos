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
    responsibleUser: responsible ? { ...responsible, email: `${responsible.id}@example.test` } : null,
    startupAt: null,
    criticality: null,
    componentsCount: 0,
  };
}

describe("groupByResponsible (GAP-011)", () => {
  it("agrupa equipamentos pelo responsável real, não por texto fixo", () => {
    const analistaA = { id: "u-analistaA", name: "Analista Sintético A" };
    const analistaD = { id: "u-analistaD", name: "Analista Sintético D" };
    const rows = [row("A", analistaA), row("B", analistaA), row("C", analistaD)];

    const groups = groupByResponsible(rows);

    expect(groups.map((g) => g.label)).toEqual(["Analista Sintético A", "Analista Sintético D"]);
    expect(groups[0]!.rows.map((r) => r.equipmentId)).toEqual(["A", "B"]);
    expect(groups[1]!.rows.map((r) => r.equipmentId)).toEqual(["C"]);
  });

  it("agrupa em ordem alfabética pelo nome do responsável", () => {
    const groups = groupByResponsible([
      row("A", { id: "u-2", name: "Analista Sintético C" }),
      row("B", { id: "u-1", name: "Analista Sintético B" }),
    ]);
    expect(groups.map((g) => g.label)).toEqual(["Analista Sintético B", "Analista Sintético C"]);
  });

  it("equipamento sem responsável cai em 'Sem responsável', sempre por último", () => {
    const groups = groupByResponsible([
      row("A", null),
      row("B", { id: "u-1", name: "Analista Sintético B" }),
    ]);
    expect(groups.map((g) => g.label)).toEqual(["Analista Sintético B", "Sem responsável"]);
    expect(groups.find((g) => g.key === NO_RESPONSIBLE_KEY)?.rows.map((r) => r.equipmentId)).toEqual([
      "A",
    ]);
  });

  it("reagrupa automaticamente quando o responsável de uma linha muda (nova chamada com dados atualizados)", () => {
    const before = groupByResponsible([row("A", { id: "u-1", name: "Analista Sintético B" })]);
    expect(before.map((g) => g.label)).toEqual(["Analista Sintético B"]);

    const after = groupByResponsible([row("A", { id: "u-2", name: "Analista Sintético D" })]);
    expect(after.map((g) => g.label)).toEqual(["Analista Sintético D"]);
  });

  it("lista vazia não gera grupos", () => {
    expect(groupByResponsible([])).toEqual([]);
  });
});
