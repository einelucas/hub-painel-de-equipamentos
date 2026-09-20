import { describe, expect, it } from "vitest";
import type { Permission } from "~/types/api";
import { NAV_ITEMS, activeNavPath, visibleNavItems } from "~/utils/navigation";

const allowAll = () => true;
const allowNone = () => false;

describe("NAV_ITEMS", () => {
  it("abre o módulo pelo Dashboard e cobre as rotas da etapa", () => {
    expect(NAV_ITEMS[0]).toMatchObject({ label: "Dashboard", to: "/dashboard" });
    expect(NAV_ITEMS.map((item) => item.to)).toEqual([
      "/dashboard",
      "/equipamentos",
      "/engenharia",
      "/juridico",
      "/suprimentos",
      "/dashboard/auditoria",
    ]);
  });

  it("dá um ícone próprio a cada item, sem repetir", () => {
    const icons = NAV_ITEMS.map((item) => item.icon);
    expect(new Set(icons).size).toBe(icons.length);
  });
});

describe("visibleNavItems", () => {
  it("esconde a auditoria de quem não tem a permissão", () => {
    const visible = visibleNavItems(NAV_ITEMS, allowNone);
    expect(visible.map((item) => item.to)).not.toContain("/dashboard/auditoria");
    expect(visible).toHaveLength(NAV_ITEMS.length - 1);
  });

  it("mostra a auditoria para quem tem audit:read", () => {
    const can = (permission: Permission) => permission === "audit:read";
    expect(visibleNavItems(NAV_ITEMS, can).map((item) => item.to)).toContain("/dashboard/auditoria");
  });

  it("mantém todos os itens sem permissão exigida", () => {
    expect(visibleNavItems(NAV_ITEMS, allowAll)).toHaveLength(NAV_ITEMS.length);
  });
});

describe("activeNavPath", () => {
  it("marca o item exato da rota atual", () => {
    expect(activeNavPath(NAV_ITEMS, "/engenharia")).toBe("/engenharia");
  });

  it("mantém Equipamentos ativo no detalhe do equipamento", () => {
    expect(activeNavPath(NAV_ITEMS, "/equipamentos/eq-123")).toBe("/equipamentos");
  });

  it("prefere o prefixo mais específico em rotas aninhadas", () => {
    expect(activeNavPath(NAV_ITEMS, "/dashboard/auditoria")).toBe("/dashboard/auditoria");
    expect(activeNavPath(NAV_ITEMS, "/dashboard")).toBe("/dashboard");
  });

  it("ignora barra final e não ativa nada fora do módulo", () => {
    expect(activeNavPath(NAV_ITEMS, "/juridico/")).toBe("/juridico");
    expect(activeNavPath(NAV_ITEMS, "/login")).toBeNull();
  });
});
