import { describe, expect, it } from "vitest";
import type { Equipment, Unit } from "~/types/equipment";
import { compatibleEquipment, equipmentRequestQuery, initialUnit } from "~/utils/equipmentFilters";

const units: Unit[] = [
  { id: "u1", code: "U1", name: "Unidade 1", active: true },
  { id: "u2", code: "U2", name: "Unidade 2", active: true },
];

describe("filtros do painel de equipamentos", () => {
  it("pré-seleciona a única unidade e preserva uma unidade válida da URL", () => {
    expect(initialUnit([units[0]!], "")).toBe("u1");
    expect(initialUnit(units, "u2")).toBe("u2");
    expect(initialUnit(units, "inexistente")).toBe("");
  });

  it("limpa um equipamento incompatível ao trocar de unidade", () => {
    const equipment = { id: "eq-1" } as Equipment;
    expect(compatibleEquipment([equipment], "eq-1")).toBe("eq-1");
    expect(compatibleEquipment([equipment], "eq-outra-unidade")).toBe("");
  });

  it("envia unidade, equipamento, busca e paginação ao backend", () => {
    expect(
      equipmentRequestQuery({ unitId: "u1", equipmentId: "eq-1", search: " bomba ", page: 2 }),
    ).toEqual({
      page: 2,
      pageSize: 25,
      sortBy: "name",
      unit_id: "u1",
      equipment_id: "eq-1",
      search: "bomba",
    });
  });
});
