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
      "/equipamentos/kanban",
    ]);
  });

  it("dá um ícone próprio a cada item, sem repetir", () => {
    const icons = NAV_ITEMS.map((item) => item.icon);
    expect(new Set(icons).size).toBe(icons.length);
  });
});

describe("visibleNavItems", () => {
  it("esconde o kanban de quem não tem a permissão", () => {
    const visible = visibleNavItems(NAV_ITEMS, allowNone);
    expect(visible.map((item) => item.to)).not.toContain("/equipamentos/kanban");
    expect(visible).toHaveLength(NAV_ITEMS.length - 1);
  });

  it("mostra o kanban para quem tem equipments:read", () => {
    const can = (permission: Permission) => permission === "equipments:read";
    expect(visibleNavItems(NAV_ITEMS, can).map((item) => item.to)).toContain("/equipamentos/kanban");
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
    expect(activeNavPath(NAV_ITEMS, "/equipamentos/kanban")).toBe("/equipamentos/kanban");
    expect(activeNavPath(NAV_ITEMS, "/equipamentos")).toBe("/equipamentos");
  });

  it("ignora barra final e não ativa nada fora do módulo", () => {
    expect(activeNavPath(NAV_ITEMS, "/juridico/")).toBe("/juridico");
    expect(activeNavPath(NAV_ITEMS, "/login")).toBeNull();
  });
});
