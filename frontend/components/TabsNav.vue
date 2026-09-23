<script setup lang="ts">
import { computed } from "vue";
import { Boxes, Kanban, LayoutDashboard, Scale, ShoppingCart, Wrench } from "lucide-vue-next";
import type { NavIcon } from "~/utils/navigation";
import { NAV_ITEMS, activeNavPath, visibleNavItems } from "~/utils/navigation";

const route = useRoute();
const auth = useAuthStore();

const ICONS = {
  dashboard: LayoutDashboard,
  equipments: Boxes,
  engineering: Wrench,
  legal: Scale,
  procurement: ShoppingCart,
  kanban: Kanban,
} satisfies Record<NavIcon, unknown>;

const items = computed(() => visibleNavItems(NAV_ITEMS, auth.can));
const active = computed(() => activeNavPath(items.value, route.path));
</script>

<template>
  <div class="app-toolbar-shell pt-2.5">
    <nav id="tabsNav" class="module-nav" aria-label="Navegação do Painel de Equipamentos">
      <NuxtLink
        v-for="item in items"
        :key="item.to"
        :to="item.to"
        class="module-nav-item"
        :class="{ 'is-active': active === item.to }"
        :aria-current="active === item.to ? 'page' : undefined"
        :aria-label="item.label"
        :data-testid="`nav-${item.icon}`"
      >
        <component :is="ICONS[item.icon]" :size="18" aria-hidden="true" />
        <!-- Rótulo só no hover/foco, como nos demais módulos do Hub. -->
        <span class="module-nav-tip" aria-hidden="true">{{ item.label }}</span>
      </NuxtLink>
    </nav>
  </div>
</template>

<style scoped>
.module-nav {
  display: flex;
  height: 70px;
  align-items: center;
  gap: 4px;
  border: 1px solid #e7ecf3;
  border-radius: 18px;
  background: #fff;
  padding: 12px 16px;
  box-shadow: 0 10px 30px rgba(39, 69, 120, .08);
  /* Sem overflow: qualquer valor diferente de visible recortaria o balão e
     criaria rolagem. Só com ícones, os itens cabem até em telas estreitas. */
}
.module-nav-item {
  position: relative;
  display: inline-flex;
  flex: 0 0 auto;
  width: 42px;
  height: 42px;
  align-items: center;
  justify-content: center;
  border: 1px solid transparent;
  border-radius: 12px;
  color: #5d6b80;
  text-decoration: none;
  transition: background .15s, color .15s, border-color .15s;
}
.module-nav-item:hover { background: #f2f6fb; color: #2b3e58; }
.module-nav-item:focus-visible { outline: 2px solid #304f7e; outline-offset: 2px; }
.module-nav-item.is-active { border-color: #d5e2f3; background: #e8f1fc; color: #27456f; }

.module-nav-tip {
  position: absolute;
  top: calc(100% + 9px);
  left: 50%;
  z-index: 30;
  border-radius: 9px;
  padding: 5px 10px;
  background: #2b3e58;
  color: #fff;
  font-size: 11.5px;
  font-weight: 700;
  white-space: nowrap;
  opacity: 0;
  pointer-events: none;
  transform: translate(-50%, -3px);
  transition: opacity .14s ease, transform .14s ease;
}
.module-nav-tip::before {
  position: absolute;
  bottom: 100%;
  left: 50%;
  border: 5px solid transparent;
  border-bottom-color: #2b3e58;
  content: "";
  transform: translateX(-50%);
}
.module-nav-item:hover .module-nav-tip,
.module-nav-item:focus-visible .module-nav-tip {
  opacity: 1;
  transform: translate(-50%, 0);
}
@media (prefers-reduced-motion: reduce) {
  .module-nav-tip { transition: none; }
}
</style>
