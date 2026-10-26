<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, useId, watch } from "vue";
import { X } from "lucide-vue-next";
import { lockBodyScroll, unlockBodyScroll } from "~/utils/bodyScrollLock";

/**
 * Modal no padrão visual do Dialog do PrimeVue, recriado localmente.
 *
 * `wide`: fluxos com tabelas e mapeamentos lado a lado (ex.: importação).
 * `contained`: altura fixa e o próprio conteúdo decide o que rola (ex.: painel
 * com índice lateral fixo); sem ele, o corpo do modal rola.
 */
const props = withDefaults(
  defineProps<{
    open: boolean;
    title: string;
    size?: "default" | "wide";
    contained?: boolean;
    /** Impede fechar pelo X, Escape ou clique no fundo enquanto salva. */
    busy?: boolean;
    /** Fecha ao clicar fora do cartão (padrão do Hub). */
    dismissableMask?: boolean;
    closeOnEscape?: boolean;
  }>(),
  {
    size: "default",
    contained: false,
    busy: false,
    dismissableMask: true,
    closeOnEscape: true,
  },
);
const emit = defineEmits<{ close: [] }>();

const titleId = `app-modal-title-${useId()}`;
const card = ref<HTMLElement | null>(null);
const previousFocus = ref<HTMLElement | null>(null);
let scrollLocked = false;

const FOCUSABLE =
  'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), ' +
  'textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

function focusableElements(): HTMLElement[] {
  if (!card.value) return [];
  return Array.from(card.value.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
    (element) => element.tabIndex >= 0 && !element.hidden,
  );
}

function requestClose(): void {
  if (!props.busy) emit("close");
}

/** Escape fecha primeiro um dropdown aberto dentro do modal; depois o modal. */
function hasOpenNestedMenu(event: KeyboardEvent): boolean {
  const target = event.target as HTMLElement | null;
  return Boolean(target?.closest('[aria-expanded="true"]'));
}

function onKeydown(event: KeyboardEvent): void {
  if (event.key === "Escape") {
    if (!props.closeOnEscape || hasOpenNestedMenu(event)) return;
    event.preventDefault();
    requestClose();
    return;
  }
  if (event.key !== "Tab" || !card.value) return;

  const focusable = focusableElements();
  if (focusable.length === 0) {
    event.preventDefault();
    card.value.focus();
    return;
  }
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  if (!first || !last) return;

  if (!card.value.contains(document.activeElement)) {
    event.preventDefault();
    first.focus();
  } else if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}

async function activate(): Promise<void> {
  previousFocus.value = document.activeElement as HTMLElement | null;
  if (!scrollLocked) {
    scrollLocked = true;
    lockBodyScroll();
  }
  await nextTick();
  if (!props.open) return;
  // Prioriza o primeiro campo do conteúdo; sem campos, o próprio cartão.
  const body = card.value?.querySelector<HTMLElement>(".modal-body");
  const first = body
    ? Array.from(body.querySelectorAll<HTMLElement>(FOCUSABLE)).find(
        (element) => element.tabIndex >= 0 && !element.hidden,
      )
    : null;
  (first ?? card.value)?.focus();
}

function deactivate(): void {
  if (scrollLocked) {
    scrollLocked = false;
    unlockBodyScroll();
  }
  const focusTarget = previousFocus.value;
  previousFocus.value = null;
  if (focusTarget?.isConnected) focusTarget.focus();
}

watch(
  () => props.open,
  (open) => {
    if (open) void activate();
    else deactivate();
  },
  { flush: "post" },
);

onMounted(() => {
  if (props.open) void activate();
});

onBeforeUnmount(() => {
  if (scrollLocked) {
    scrollLocked = false;
    unlockBodyScroll();
  }
});
</script>

<template>
  <Teleport to="body">
    <Transition name="app-modal">
      <div
        v-if="open"
        class="modal-backdrop"
        @mousedown.self="dismissableMask && requestClose()"
      >
        <section
          ref="card"
          class="modal-card"
          :class="{
            'modal-card--wide': size === 'wide',
            'modal-card--contained': contained,
          }"
          role="dialog"
          aria-modal="true"
          :aria-labelledby="titleId"
          tabindex="-1"
          @keydown="onKeydown"
        >
          <header class="modal-header">
            <h2 :id="titleId">{{ title }}</h2>
            <button
              type="button"
              class="modal-close"
              aria-label="Fechar"
              :disabled="busy"
              @click="requestClose"
            >
              <X :size="20" aria-hidden="true" />
            </button>
          </header>
          <div class="modal-body"><slot /></div>
          <footer v-if="$slots.actions" class="modal-actions"><slot name="actions" /></footer>
        </section>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: grid;
  place-items: center;
  padding: 20px;
  background: rgb(16 24 40 / 45%);
}

.modal-card {
  display: grid;
  width: min(680px, 100%);
  max-height: calc(100vh - 40px);
  max-height: calc(100dvh - 40px);
  grid-template-rows: auto minmax(0, 1fr) auto;
  overflow: hidden;
  border: 1px solid #e1e8f1;
  border-radius: 12px;
  background: #fff;
  box-shadow: 0 24px 70px rgb(15 30 55 / 30%);
  color: #1f3352;
}

.modal-card:focus { outline: none; }
.modal-card--wide { width: min(1040px, 100%); }

.modal-card--contained {
  height: min(820px, calc(100vh - 40px));
  height: min(820px, calc(100dvh - 40px));
}

.modal-card--contained .modal-body {
  overflow: hidden;
  padding-bottom: 0;
}

.modal-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  border-bottom: 1px solid #e9edf2;
  padding: 17px 20px 15px;
}

.modal-header h2 {
  margin: 0;
  color: #1f3352;
  font-size: 18px;
  font-weight: 800;
  letter-spacing: -0.01em;
  line-height: 1.3;
}

.modal-close {
  display: inline-grid;
  flex: 0 0 auto;
  width: 30px;
  height: 30px;
  place-items: center;
  border: 0;
  border-radius: 7px;
  margin: -4px -6px 0 0;
  background: transparent;
  color: #95a1b1;
  cursor: pointer;
}

.modal-close:hover:not(:disabled) { background: #f0f4f9; color: #526176; }
.modal-close:focus-visible { outline: 2px solid #304f7e; outline-offset: 1px; }
.modal-close:disabled { opacity: 0.45; cursor: not-allowed; }

.modal-body {
  min-height: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
  padding: 20px;
}

.modal-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 9px;
  border-top: 1px solid #e9edf2;
  padding: 14px 20px 16px;
  background: #fbfcfe;
}

.app-modal-enter-active,
.app-modal-leave-active { transition: opacity 0.16s ease; }

.app-modal-enter-active .modal-card,
.app-modal-leave-active .modal-card { transition: transform 0.16s ease, opacity 0.16s ease; }

.app-modal-enter-from,
.app-modal-leave-to { opacity: 0; }

.app-modal-enter-from .modal-card,
.app-modal-leave-to .modal-card { opacity: 0; transform: translateY(6px) scale(0.985); }

@media (max-width: 640px) {
  .modal-backdrop { padding: 12px; }
  .modal-card { max-height: calc(100vh - 24px); max-height: calc(100dvh - 24px); }
  .modal-card--contained { height: calc(100vh - 24px); height: calc(100dvh - 24px); }
  .modal-header { padding: 15px 17px 13px; }
  .modal-body { padding: 16px 20px 20px; }
  .modal-actions { padding: 13px 17px 15px; }
}

@media (prefers-reduced-motion: reduce) {
  .app-modal-enter-active,
  .app-modal-leave-active,
  .app-modal-enter-active .modal-card,
  .app-modal-leave-active .modal-card { transition: none; }
}
</style>
