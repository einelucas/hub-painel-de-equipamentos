import type { Permission } from "~/types/api";

export type NavIcon =
  | "dashboard"
  | "equipments"
  | "engineering"
  | "legal"
  | "procurement"
  | "audit";

export interface NavItem {
  label: string;
  to: string;
  icon: NavIcon;
  /** Quando presente, o item só aparece para quem tem a permissão. */
  permission?: Permission;
}

export const NAV_ITEMS: NavItem[] = [
  { label: "Dashboard", to: "/dashboard", icon: "dashboard" },
  { label: "Equipamentos", to: "/equipamentos", icon: "equipments" },
  { label: "Engenharia", to: "/engenharia", icon: "engineering" },
  { label: "Jurídico", to: "/juridico", icon: "legal" },
  { label: "Suprimentos", to: "/suprimentos", icon: "procurement" },
  { label: "Auditoria", to: "/dashboard/auditoria", icon: "audit", permission: "audit:read" },
];

export function visibleNavItems(
  items: NavItem[],
  can: (permission: Permission) => boolean,
): NavItem[] {
  return items.filter((item) => !item.permission || can(item.permission));
}

/**
 * Rota ativa por prefixo mais específico: `/dashboard/auditoria` ativa
 * Auditoria, não Dashboard, e `/equipamentos/{id}` ativa Equipamentos.
 */
export function activeNavPath(items: NavItem[], currentPath: string): string | null {
  const normalized = currentPath.replace(/\/+$/, "") || "/";
  let best: string | null = null;
  for (const item of items) {
    const matches = normalized === item.to || normalized.startsWith(`${item.to}/`);
    if (matches && (best === null || item.to.length > best.length)) best = item.to;
  }
  return best;
}
