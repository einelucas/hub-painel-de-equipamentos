<script setup lang="ts">
import { ChevronDown, LogOut } from "lucide-vue-next";

const ROLE_LABELS: Record<string, string> = {
  VIEWER: "Visualizador",
  ANALYST: "Analista",
  ADMIN: "Administrador",
};

function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  const first = parts[0]?.[0] ?? "";
  const last = parts.length > 1 ? (parts[parts.length - 1]?.[0] ?? "") : "";
  return (first + last).toUpperCase();
}

const { store, logout } = useAuth();
const open = ref(false);
const rootRef = ref<HTMLElement | null>(null);

function onClickOutside(event: MouseEvent): void {
  if (rootRef.value && !rootRef.value.contains(event.target as Node)) open.value = false;
}

watch(open, (isOpen) => {
  if (isOpen) document.addEventListener("mousedown", onClickOutside);
  else document.removeEventListener("mousedown", onClickOutside);
});
onBeforeUnmount(() => document.removeEventListener("mousedown", onClickOutside));

const { pending: loggingOut, run: runLogout } = useAsyncAction(logout);

async function handleLogout(): Promise<void> {
  if (loggingOut.value) return;
  await runLogout();
  open.value = false;
}
</script>

<template>
  <div ref="rootRef" class="user-menu">
    <button
      type="button"
      class="user-menu__trigger"
      aria-haspopup="menu"
      :aria-expanded="open"
      aria-label="Abrir menu do usuário"
      @click="open = !open"
    >
      <span class="user-menu__avatar">
        {{ initials(store.user?.name || "?") }}
        <span class="user-menu__status" aria-hidden="true" />
      </span>
      <ChevronDown
        class="user-menu__chevron"
        :class="{ 'user-menu__chevron--open': open }"
        :size="15"
        stroke-width="1.8"
        aria-hidden="true"
      />
    </button>

    <div v-if="open" role="menu" class="user-menu__dropdown">
      <div class="user-menu__profile">
        <strong>{{ store.user?.name }}</strong>
        <span>{{ store.user ? ROLE_LABELS[store.user.role] : "" }}</span>
      </div>
      <div class="user-menu__divider" />
      <button
        type="button"
        class="user-menu__logout"
        :disabled="loggingOut"
        :aria-busy="loggingOut"
        @click="handleLogout"
      >
        <LogOut v-if="!loggingOut" :size="16" stroke-width="1.8" aria-hidden="true" />
        <span v-else class="user-menu__spinner" aria-hidden="true" />
        {{ loggingOut ? "Saindo..." : "Sair" }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.user-menu { position: relative; flex: 0 0 auto; }

.user-menu__trigger {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-width: 66px;
  height: 48px;
  padding: 0 2px 0 4px;
  border: 0;
  background: transparent;
  color: #5d6b7f;
}

.user-menu__trigger:focus-visible { outline: 2px solid rgb(48 79 126 / 24%); outline-offset: 1px; border-radius: 8px; }
.user-menu__avatar { position: relative; display: inline-flex; align-items: center; justify-content: center; width: 40px; height: 40px; border-radius: 50%; background: #f0f3f7; color: #304f7e; font-size: 12px; font-weight: 800; }
.user-menu__status { position: absolute; right: 1px; bottom: 1px; width: 9px; height: 9px; border: 2px solid #fff; border-radius: 50%; background: #609346; }
.user-menu__chevron { transition: transform 150ms ease; }
.user-menu__chevron--open { transform: rotate(180deg); }

.user-menu__dropdown { position: absolute; top: calc(100% + 7px); right: 0; z-index: 40; width: 224px; padding: 7px; border: 1px solid #e2e7ee; border-radius: 11px; background: #fff; box-shadow: 0 12px 28px rgb(20 37 62 / 16%); }
.user-menu__profile { display: grid; gap: 3px; padding: 9px 10px; }
.user-menu__profile strong { overflow: hidden; color: #1d304b; font-size: 13px; text-overflow: ellipsis; white-space: nowrap; }
.user-menu__profile span { color: #748197; font-size: 11px; }
.user-menu__divider { height: 1px; margin: 3px 0 6px; background: #edf0f4; }

.user-menu__logout { display: flex; align-items: center; justify-content: center; gap: 7px; width: 100%; height: 34px; border: 0; border-radius: 7px; background: #fceceb; color: #b43b32; font-size: 12px; font-weight: 650; }
.user-menu__logout:hover { background: #f8dfdd; }
.user-menu__logout:disabled { cursor: wait; opacity: 0.65; }
.user-menu__spinner { width: 14px; height: 14px; border: 2px solid currentColor; border-right-color: transparent; border-radius: 50%; animation: user-menu-spin 650ms linear infinite; }

@keyframes user-menu-spin { to { transform: rotate(360deg); } }
</style>
