import { describe, expect, it } from "vitest";
import type { CurrentUser } from "~/types/api";
import { hasPermission } from "~/utils/permissions";

function user(role: CurrentUser["role"], permissions: CurrentUser["permissions"]): CurrentUser {
  return { id: "u1", email: "u@x.com", name: "U", role, active: true, permissions };
}

describe("hasPermission (GAP-016 — fonte única é o backend, sem matriz local)", () => {
  it("VIEWER só tem as permissões de leitura devolvidas pelo backend", () => {
    const viewer = user("VIEWER", ["equipments:read", "catalogs:read", "workflow:read", "suppliers:read"]);
    expect(hasPermission(viewer, "equipments:read")).toBe(true);
    expect(hasPermission(viewer, "catalogs:read")).toBe(true);
    expect(hasPermission(viewer, "equipments:write")).toBe(false);
    expect(hasPermission(viewer, "audit:read")).toBe(false);
  });

  it("ANALYST tem leitura + escrita, mas não administração", () => {
    const analyst = user("ANALYST", [
      "equipments:read",
      "catalogs:read",
      "workflow:read",
      "suppliers:read",
      "equipments:write",
      "process:write",
      "workflow:transition",
      "suppliers:write",
    ]);
    expect(hasPermission(analyst, "equipments:write")).toBe(true);
    expect(hasPermission(analyst, "workflow:transition")).toBe(true);
    expect(hasPermission(analyst, "workflow:reopen")).toBe(false);
    expect(hasPermission(analyst, "users:manage")).toBe(false);
    expect(hasPermission(analyst, "audit:read")).toBe(false);
  });

  it("ADMIN tem tudo, incluindo administração", () => {
    const admin = user("ADMIN", [
      "equipments:read",
      "catalogs:read",
      "workflow:read",
      "suppliers:read",
      "equipments:write",
      "process:write",
      "workflow:transition",
      "suppliers:write",
      "users:manage",
      "audit:read",
      "catalogs:manage",
      "workflow:reopen",
    ]);
    expect(hasPermission(admin, "users:manage")).toBe(true);
    expect(hasPermission(admin, "audit:read")).toBe(true);
    expect(hasPermission(admin, "catalogs:manage")).toBe(true);
    expect(hasPermission(admin, "workflow:reopen")).toBe(true);
  });

  it("nega tudo quando não há usuário autenticado", () => {
    expect(hasPermission(null, "equipments:read")).toBe(false);
  });

  it("nega tudo quando `permissions` está ausente (nunca assume acesso não confirmado pelo backend)", () => {
    expect(hasPermission(user("ADMIN", undefined), "equipments:read")).toBe(false);
  });
});
