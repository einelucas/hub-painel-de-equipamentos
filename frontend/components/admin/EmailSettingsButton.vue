<script setup lang="ts">
import { Mail } from "lucide-vue-next";

/**
 * Ação da barra do módulo: atalho para a central de e-mails (regras,
 * destinatários, modelos e caixa de testes). A página de destino continua
 * protegida pelo middleware/backend de ADMIN.
 */
</script>

<template>
  <NuxtLink
    to="/administracao/notificacoes"
    class="module-action"
    aria-label="Configurar e-mails"
    data-testid="nav-email-settings"
  >
    <Mail :size="18" aria-hidden="true" />
    <span class="module-action-tip" aria-hidden="true">Configurar e-mails</span>
  </NuxtLink>
</template>

<style scoped>
/* Mesma geometria dos itens da TabsNav (42px, raio 12px) para não alterar a altura da barra. */
.module-action { position: relative; display: inline-flex; flex: 0 0 auto; width: 42px; height: 42px; align-items: center; justify-content: center; border: 1px solid transparent; border-radius: 12px; background: transparent; color: #5d6b80; text-decoration: none; transition: background .15s, color .15s; }
.module-action:hover { background: #f2f6fb; color: #2b3e58; }
.module-action:focus-visible { outline: 2px solid #304f7e; outline-offset: 2px; }
.module-action-tip { position: absolute; top: calc(100% + 9px); left: 50%; z-index: 30; border-radius: 9px; padding: 5px 10px; background: #2b3e58; color: #fff; font-size: 11.5px; font-weight: 700; white-space: nowrap; opacity: 0; pointer-events: none; transform: translate(-50%, -3px); transition: opacity .14s ease, transform .14s ease; }
.module-action-tip::before { position: absolute; bottom: 100%; left: 50%; border: 5px solid transparent; border-bottom-color: #2b3e58; content: ""; transform: translateX(-50%); }
.module-action:hover .module-action-tip, .module-action:focus-visible .module-action-tip { opacity: 1; transform: translate(-50%, 0); }
@media (prefers-reduced-motion: reduce) { .module-action-tip { transition: none; } }
</style>
