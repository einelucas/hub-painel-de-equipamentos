import { describe, expect, it } from "vitest";
import { equipmentLocationLabel } from "~/utils/equipmentLocation";

describe("equipmentLocationLabel", () => {
  it("usa código e nome da EAP canônica", () => {
    expect(equipmentLocationLabel({
      eapNode: { id: "e1", code: "04.A", name: "Casa de Força", level: "AREA", active: true },
      area: { id: "a1", name: "Área legada" },
    })).toBe("04.A · Casa de Força");
  });

  it("mantém a área legada somente como fallback", () => {
    expect(equipmentLocationLabel({
      eapNode: null,
      area: { id: "a1", name: "Área legada" },
    })).toBe("Área legada");
  });

  it("retorna nulo quando não há localização", () => {
    expect(equipmentLocationLabel({ eapNode: null, area: null })).toBeNull();
  });
});
