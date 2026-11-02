<script setup lang="ts">
import { ArrowLeft, Bell, CloudDownload, History, Search } from "lucide-vue-next";

const router = useRouter();
const { store } = useAuth();
</script>

<template>
  <header class="app-header">
    <div class="app-header__identity">
      <NuxtLink to="/dashboard" class="app-header__brand" aria-label="Painel de Equipamentos">
        <img src="/brand/hub-logo.png" alt="Automação Industrial" />
      </NuxtLink>

      <button class="app-header__back" type="button" @click="router.back()">
        <ArrowLeft :size="17" stroke-width="1.8" aria-hidden="true" />
        <span>Voltar</span>
      </button>

      <div class="app-header__context">
        <span>Planejamento</span>
        <strong>Painel de Equipamentos</strong>
      </div>
    </div>

    <label class="app-header__search">
      <Search :size="17" stroke-width="1.8" aria-hidden="true" />
      <input type="search" placeholder="Buscar" aria-label="Buscar no módulo" />
    </label>

    <div class="app-header__actions">
      <button class="app-header__icon-button" type="button" aria-label="Notificações" title="Notificações do Hub">
        <Bell :size="18" stroke-width="1.7" aria-hidden="true" />
      </button>

      <NuxtLink v-if="store.user?.role === 'ADMIN'" to="/dashboard/auditoria" class="app-header__activity">
        <History :size="16" stroke-width="1.8" aria-hidden="true" />
        <span>Registro de Atividades</span>
      </NuxtLink>

      <button class="app-header__icon-button" type="button" aria-label="Exportar dados" title="Exportação disponível quando houver dados no módulo">
        <CloudDownload :size="18" stroke-width="1.7" aria-hidden="true" />
      </button>

      <UserMenu />
    </div>
  </header>
</template>

<style scoped>
.app-header {
  position: relative;
  z-index: 30;
  display: flex;
  align-items: center;
  width: 100%;
  height: 64px;
  padding: 0 20px;
  border-bottom: 1px solid #e7e9ed;
  background: #fff;
  color: #182b47;
}

.app-header__identity,
.app-header__actions {
  display: flex;
  align-items: center;
  min-width: 0;
}

.app-header__identity { gap: 12px; }
.app-header__actions { gap: 6px; margin-left: auto; }

.app-header__brand {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  width: 120px;
  height: 38px;
}

.app-header__brand img { display: block; width: 100%; height: auto; }

.app-header__back {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  gap: 8px;
  height: 38px;
  padding: 0 12px;
  border: 1px solid #dfe3e9;
  border-radius: 8px;
  background: #fff;
  color: #283a54;
  font-size: 14px;
  font-weight: 500;
  line-height: 1;
  transition: border-color 150ms ease, background-color 150ms ease;
}

.app-header__back:hover { border-color: #cbd2dc; background: #f8f9fb; }
.app-header__back:focus-visible,
.app-header__icon-button:focus-visible,
.app-header__activity:focus-visible,
.app-header__search:focus-within {
  outline: 2px solid rgb(48 79 126 / 24%);
  outline-offset: 2px;
}

.app-header__context { display: grid; min-width: 0; gap: 5px; }
.app-header__context span { color: #8492a7; font-size: 9.5px; font-weight: 800; letter-spacing: 0.09em; line-height: 1; text-transform: uppercase; }
.app-header__context strong { color: #142742; font-size: 16px; font-weight: 800; line-height: 1; white-space: nowrap; }

.app-header__search {
  position: absolute;
  top: 11px;
  left: calc(50% + 14px);
  display: flex;
  align-items: center;
  gap: 10px;
  width: min(480px, 30vw);
  height: 42px;
  padding: 0 15px;
  border: 1px solid #eef0f3;
  border-radius: 999px;
  background: #fff;
  box-shadow: 0 2px 5px rgb(15 35 63 / 10%);
  color: #69778b;
  transform: translateX(-50%);
  transition: border-color 150ms ease, box-shadow 150ms ease;
}

.app-header__search:focus-within { border-color: #cfd7e2; box-shadow: 0 3px 9px rgb(15 35 63 / 13%); }
.app-header__search input { min-width: 0; flex: 1; border: 0; outline: 0; background: transparent; color: #253750; font-size: 14px; line-height: 1; }
.app-header__search input::placeholder { color: #718096; opacity: 1; }
.app-header__search input::-webkit-search-cancel-button { display: none; }

.app-header__icon-button {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  padding: 0;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: #5d6b7f;
  transition: background-color 150ms ease, color 150ms ease;
}

.app-header__icon-button:hover { background: #f3f5f8; color: #304f7e; }

.app-header__activity {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 7px;
  height: 34px;
  padding: 0 14px;
  border-radius: 5px;
  background: #eef2f8;
  color: #294978;
  font-size: 13px;
  font-weight: 600;
  text-decoration: none;
  transition: background-color 150ms ease;
}

.app-header__activity:hover { background: #e5ebf4; }

@media (max-width: 1260px) {
  .app-header__search { width: 330px; }
  .app-header__context { display: none; }
}

@media (max-width: 900px) {
  .app-header { padding: 0 14px; }
  .app-header__brand { width: 104px; }
  .app-header__search { display: none; }
  .app-header__activity span { display: none; }
  .app-header__activity { width: 36px; padding: 0; justify-content: center; }
}

@media (max-width: 560px) {
  .app-header__brand { width: 92px; }
  .app-header__back span { display: none; }
  .app-header__back { width: 36px; padding: 0; }
  .app-header__actions { gap: 2px; }
}
</style>
