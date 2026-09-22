import type { CurrentUser, Permission } from "~/types/api";

/**
 * GAP-016 (Etapa 6D) — única fonte de verdade é `user.permissions`,
 * devolvido pelo backend (`app.core.permissions.permissions_for`) em
 * `/auth/me`. Nenhuma matriz de papel→permissão é replicada no frontend;
 * sem o array (usuário nulo ou sessão antiga sem o campo), nega o acesso
 * em vez de assumir uma permissão que o backend não confirmou.
 */
export function hasPermission(user: CurrentUser | null, permission: Permission): boolean {
  return Boolean(user?.permissions?.includes(permission));
}
