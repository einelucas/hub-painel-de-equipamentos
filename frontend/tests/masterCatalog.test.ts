import { describe, expect, it } from "vitest";
import type { MasterArea, MasterEquipment } from "~/types/masterCatalog";
import {
  areaNames,
  areaSummary,
  areaUsage,
  buildAreaMap,
  componentCountLabel,
  filterEquipments,
  fullAreaSummary,
  inactiveLinkedAreas,
  isAreaDraftDirty,
  plural,
} from "~/utils/masterCatalog";

const areas: MasterArea[] = [
  { id: "utilidades", name: "Utilidades", active: true, isUnassigned: false },
  { id: "eletrica", name: "Elétrica", active: true, isUnassigned: false },
  { id: "antiga", name: "Área antiga", active: false, isUnassigned: false },
  { id: "sem-area", name: "Sem área definida", active: true, isUnassigned: true },
];

function equipment(overrides: Partial<MasterEquipment> = {}): MasterEquipment {
  return {
    id: "equipamento",
    name: "Bomba centrífuga",
    areaIds: ["utilidades"],
    components: [],
    active: true,
    reviewFlags: [],
    ...overrides,
  };
}

describe("catálogo mestre", () => {
  it("resume áreas ignorando vínculos desconhecidos", () => {
    const areaMap = buildAreaMap(areas);

    expect(areaNames(equipment({ areaIds: ["utilidades", "removida"] }), areaMap)).toEqual([
      "Utilidades",
    ]);
    expect(areaSummary(equipment(), areaMap)).toBe("Utilidades");
    expect(areaSummary(equipment({ areaIds: ["utilidades", "eletrica"] }), areaMap)).toBe(
      "Utilidades +1",
    );
    expect(areaSummary(equipment({ areaIds: [] }), areaMap)).toBe("Sem área definida");
    expect(fullAreaSummary(equipment({ areaIds: ["utilidades", "eletrica"] }), areaMap)).toBe(
      "Utilidades · Elétrica",
    );
  });

  it("descreve o uso das áreas sem confundir a categoria virtual", () => {
    const items = [
      equipment({ id: "bomba", areaIds: ["utilidades"] }),
      equipment({ id: "painel", areaIds: ["utilidades", "eletrica"] }),
    ];

    expect(areaUsage(areas[0]!, items)).toBe("2 equipamentos vinculados");
    expect(areaUsage(areas[0]!, [])).toBe("Nenhum equipamento vinculado");
    expect(areaUsage(areas[3]!, items)).toBe(
      "Categoria de sistema para modelos não classificados",
    );
    expect(plural(1, "equipamento", "equipamentos")).toBe("1 equipamento");
    expect(plural(0, "equipamento", "equipamentos")).toBe("0 equipamentos");
    expect(componentCountLabel(3)).toBe("3 componentes");
  });

  it("filtra por nome e por área, incluindo a categoria sem área", () => {
    const items = [
      equipment({ id: "bomba", name: "Bomba centrífuga", areaIds: ["utilidades"] }),
      equipment({ id: "painel", name: "Painel elétrico", areaIds: ["eletrica"] }),
      equipment({ id: "avulso", name: "Bomba avulsa", areaIds: [] }),
    ];

    expect(filterEquipments(items, areas, "BOMBA", "").map((item) => item.id)).toEqual([
      "bomba",
      "avulso",
    ]);
    expect(filterEquipments(items, areas, "", "utilidades").map((item) => item.id)).toEqual([
      "bomba",
    ]);
    expect(filterEquipments(items, areas, "", "unassigned").map((item) => item.id)).toEqual([
      "avulso",
    ]);
    expect(
      filterEquipments(
        [equipment({ areaIds: ["sem-area"] })],
        areas,
        "",
        "unassigned",
      ),
    ).toHaveLength(1);
  });

  it("detecta alterações de áreas e vínculos inativos", () => {
    const item = equipment({ areaIds: ["utilidades", "antiga"] });
    const areaMap = buildAreaMap(areas);

    expect(isAreaDraftDirty(item, ["antiga", "utilidades"])).toBe(false);
    expect(isAreaDraftDirty(item, ["utilidades"])).toBe(true);
    expect(isAreaDraftDirty(item, [])).toBe(true);
    expect(inactiveLinkedAreas(item, areaMap).map((area) => area.id)).toEqual(["antiga"]);
  });
});
