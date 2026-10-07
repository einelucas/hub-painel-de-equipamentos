import { defineStore } from "pinia";
import type { CurrentUser, Permission } from "~/types/api";
import { hasPermission } from "~/utils/permissions";

export const useAuthStore = defineStore("auth", () => {
  const token = useCookie<string | null>("painel_equipamentos_access_token", { sameSite: "lax" });
  const user = ref<CurrentUser | null>(null);
  const loading = ref(false);

  const authenticated = computed(() => Boolean(token.value && user.value));
  const isAdmin = computed(() => user.value?.role === "ADMIN");
  const can = (permission: Permission) => hasPermission(user.value, permission);

  async function loadUser(): Promise<boolean> {
    if (!token.value) {
      user.value = null;
      return false;
    }
    loading.value = true;
    try {
      user.value = await useApi().get<CurrentUser>("/auth/me");
      return true;
    } catch {
      token.value = null;
      user.value = null;
      return false;
    } finally {
      loading.value = false;
    }
  }

  /** Login local: e-mail e senha conferidos pelo backend contra o banco. */
  async function loginWithPassword(email: string, password: string): Promise<void> {
    const session = await useApi().post<{ accessToken: string }>("/auth/login", { email, password });
    token.value = session.accessToken;
    if (!(await loadUser())) throw new Error("A API recusou a sessão recebida.");
  }

  /** Encerra a sessão local no backend; tokens OIDC só são descartados. */
  async function revokeSession(): Promise<void> {
    if (!token.value) return;
    try {
      await useApi().post("/auth/logout");
    } catch {
      // Sessão já expirada ou API fora do ar: o token é descartado de qualquer forma.
    }
  }

  function acceptToken(accessToken: string): void {
    token.value = accessToken;
  }

  function clear(): void {
    token.value = null;
    user.value = null;
  }

  return { token, user, loading, authenticated, isAdmin, can, loadUser, loginWithPassword, revokeSession, acceptToken, clear };
});
