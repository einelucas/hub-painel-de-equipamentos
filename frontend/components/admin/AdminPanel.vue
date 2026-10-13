<script setup lang="ts">
import { computed, watch } from "vue";

/**
 * Casca do painel administrativo contextual.
 *
 * Mora dentro da aba onde o dado é usado — o usuário não sai da tela. Só cuida
 * de layout, navegação e estados; cada seção traz seu próprio conteúdo por slot.
 * Com mais de uma seção, a navegação vira um índice lateral; seções com
 * `children` (ex.: Catálogos) listam seus itens aninhados, sem segunda barra.
 */
export interface AdminPanelItem {
  key: string;
  label: string;
  /** Uma linha sobre o que o item guarda; aparece sob o rótulo no índice. */
  hint?: string;
}

export interface AdminPanelSection extends AdminPanelItem {
  children?: AdminPanelItem[];
  /** Prefixo do data-testid dos itens filhos (ex.: "catalog-switch"). */
  childTestId?: string;
}

const props = defineProps<{
  open: boolean;
  title: string;
  description: string;
  sections: AdminPanelSection[];
  /**
   * Altura fixa com rolagem só no conteúdo. Painéis com índice lateral já são
   * contidos; um painel de seção única (ex.: Fornecedores) pode pedir o mesmo.
   */
  contained?: boolean;
}>();
const emit = defineEmits<{ close: [] }>();
const isContained = computed(() => props.contained || props.sections.length > 1);

const active = defineModel<string>("section", { required: true });
/** Item filho ativo da seção atual (quando a seção tem `children`). */
const item = defineModel<string>("item", { default: "" });

watch(
  () => props.open,
  (isOpen) => {
    if (isOpen && !props.sections.some((section) => section.key === active.value)) {
      active.value = props.sections[0]?.key ?? "";
    }
  },
);

function openChild(section: AdminPanelSection, child: AdminPanelItem): void {
  active.value = section.key;
  item.value = child.key;
}
</script>

<template>
  <AppModal
    :open="props.open"
    :title="props.title"
    size="wide"
    :contained="isContained"
    @close="emit('close')"
  >
    <div
      class="admin-panel"
      :class="{ 'admin-panel--indexed': props.sections.length > 1, 'admin-panel--contained': isContained }"
      data-testid="admin-panel"
    >
      <nav v-if="props.sections.length > 1" class="admin-index" aria-label="Seções da administração">
        <p class="admin-description">{{ props.description }}</p>
        <div class="admin-index-list" role="tablist" aria-orientation="vertical">
          <template v-for="section in props.sections" :key="section.key">
            <button
              type="button"
              role="tab"
              class="admin-index-item"
              :class="{ active: active === section.key }"
              :aria-selected="active === section.key"
              :data-hint="section.hint"
              :data-testid="`admin-tab-${section.key}`"
              @click="active = section.key"
            >
              {{ section.label }}
            </button>
            <div v-if="section.children?.length" class="admin-index-children" role="group" :aria-label="section.label">
              <button
                v-for="child in section.children"
                :key="child.key"
                type="button"
                class="admin-index-child"
                :class="{ active: active === section.key && item === child.key }"
                :aria-current="active === section.key && item === child.key ? 'page' : undefined"
                :data-testid="`${section.childTestId ?? 'admin-item'}-${child.key}`"
                @click="openChild(section, child)"
              >
                {{ child.label }}
              </button>
            </div>
          </template>
        </div>
      </nav>
      <p v-else class="admin-description admin-description--solo">{{ props.description }}</p>

      <div class="admin-body">
        <slot :section="active" />
      </div>
    </div>
  </AppModal>
</template>

<style scoped>
/* Mesmos tokens da importação: o Hub fala a mesma língua visual nos modais largos. */
.admin-panel {
  --ink: #1f3352;
  --steel: #304f7e;
  --wash: #f3f6fb;
  --rule: #dde5ef;
  --muted: #6b7a8f;
  --go: #3f7a2e;
  --go-wash: #eaf4e5;
  --stop: #a4453a;
  --stop-wash: #fbeeed;
  --mono: ui-monospace, "Cascadia Mono", "SFMono-Regular", Consolas, monospace;

  display: grid;
  gap: 16px;
}
/* Contido: altura do modal; índice (quando houver) parado, só o conteúdo rola. */
.admin-panel--contained { height: 100%; grid-template-rows: auto minmax(0, 1fr); }
.admin-panel--indexed { grid-template-rows: none; grid-template-columns: 232px minmax(0, 1fr); align-items: stretch; gap: 22px; }
/*
 * Coluna flex: seções comuns crescem e o corpo rola; seções de lista
 * (`.admin-fill`) ocupam a altura restante e rolam só a própria lista.
 */
.admin-panel--contained .admin-body { display: flex; min-height: 0; flex-direction: column; overflow-y: auto; padding: 0 6px 20px 2px; }
.admin-panel--contained .admin-body > :deep(.admin-fill) { min-height: 0; flex: 1 1 0; }

.admin-description { margin: 0; color: var(--muted); font-size: 12px; line-height: 1.45; }
.admin-description--solo { font-size: 12.5px; }

/* ---------- Índice lateral ---------- */
.admin-index {
  display: grid;
  align-content: start;
  gap: 14px;
  min-height: 0;
  overflow-y: auto;
  padding: 2px 18px 20px 0;
  border-right: 1px solid var(--rule);
}
.admin-index-list { display: grid; gap: 2px; }
.admin-index-item {
  position: relative;
  display: grid;
  gap: 1px;
  border: 0;
  border-radius: 10px;
  padding: 9px 12px 9px 14px;
  background: transparent;
  color: var(--ink);
  font-size: 13px;
  font-weight: 800;
  text-align: left;
  cursor: pointer;
}
/* Descrição do item via CSS: não entra no nome acessível da aba. */
.admin-index-item[data-hint]::after {
  color: var(--muted);
  font-size: 11px;
  font-weight: 600;
  content: attr(data-hint);
}
.admin-index-item::before {
  position: absolute;
  top: 10px;
  bottom: 10px;
  left: 0;
  width: 3px;
  border-radius: 3px;
  background: transparent;
  content: "";
}
.admin-index-item:hover { background: var(--wash); }
.admin-index-item.active { background: #e8f1fc; }
.admin-index-item.active::before { background: var(--steel); }

.admin-index-children { display: grid; gap: 1px; margin: 2px 0 6px 14px; padding-left: 10px; border-left: 1px solid var(--rule); }
.admin-index-child {
  border: 0;
  border-radius: 8px;
  padding: 6px 10px;
  background: transparent;
  color: var(--muted);
  font-size: 12px;
  font-weight: 700;
  text-align: left;
  cursor: pointer;
}
.admin-index-child:hover { background: var(--wash); color: var(--ink); }
.admin-index-child.active { background: var(--ink); color: #fff; }
.admin-index-item:focus-visible, .admin-index-child:focus-visible { outline: 2px solid var(--steel); outline-offset: 2px; }

.admin-body { min-width: 0; }

@media (max-width: 820px) {
  .admin-panel--indexed { grid-template-columns: 1fr; grid-template-rows: auto minmax(0, 1fr); gap: 12px; }
  .admin-index { overflow: visible; padding: 0 0 12px; border-right: 0; border-bottom: 1px solid var(--rule); }
  .admin-index-list { grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); }
}
</style>
