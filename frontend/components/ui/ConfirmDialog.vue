<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue";
import { AlertTriangle, Info, Trash2, X } from "lucide-vue-next";
import AppTeleport from "~/components/ui/AppTeleport.vue";
import { useConfirm } from "~/composables/useConfirm";
import { lockBodyScroll, unlockBodyScroll } from "~/utils/bodyScrollLock";

/**
 * Diálogo de confirmação global no padrão visual do ConfirmDialog do PrimeVue,
 * recriado localmente (sem instalar a biblioteca).
 */
const { state, accept, cancel } = useConfirm();

const card = ref<HTMLElement | null>(null);
const cancelButton = ref<HTMLButtonElement | null>(null);
let previousFocus: HTMLElement | null = null;
let scrollLocked = false;

const iconComponent = computed(() => {
  if (state.icon === "trash") return Trash2;
  if (state.icon === "warning") return AlertTriangle;
  return Info;
});

const FOCUSABLE =
  'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), ' +
  'textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

function onKeydown(event: KeyboardEvent): void {
  if (event.key === "Escape") {
    event.preventDefault();
    cancel();
    return;
  }
  if (event.key !== "Tab" || !card.value) return;
  const focusable = Array.from(card.value.querySelectorAll<HTMLElement>(FOCUSABLE));
  if (!focusable.length) return;
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  if (!first || !last) return;
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}

watch(
  () => state.open,
  async (open) => {
    if (open) {
      previousFocus = document.activeElement as HTMLElement | null;
      if (!scrollLocked) {
        scrollLocked = true;
        lockBodyScroll();
      }
      await nextTick();
      cancelButton.value?.focus();
    } else {
      if (scrollLocked) {
        scrollLocked = false;
        unlockBodyScroll();
      }
      previousFocus?.focus?.();
      previousFocus = null;
    }
  },
);

onBeforeUnmount(() => {
  if (scrollLocked) {
    scrollLocked = false;
    unlockBodyScroll();
  }
});
</script>

<template>
  <AppTeleport>
    <Transition name="confirm-fade">
      <div v-if="state.open" class="confirm-backdrop" @mousedown.self="cancel">
        <section
          ref="card"
          class="confirm-card"
          role="alertdialog"
          aria-modal="true"
          aria-labelledby="confirm-dialog-title"
          aria-describedby="confirm-dialog-message"
          @keydown="onKeydown"
        >
          <header class="confirm-head">
            <h2 id="confirm-dialog-title">{{ state.title }}</h2>
            <button type="button" class="confirm-close" aria-label="Fechar" @click="cancel">
              <X :size="20" aria-hidden="true" />
            </button>
          </header>

          <div class="confirm-body">
            <span class="confirm-icon" :class="`confirm-icon--${state.tone}`" aria-hidden="true">
              <component :is="iconComponent" :size="22" />
            </span>
            <div class="confirm-copy">
              <p id="confirm-dialog-message">{{ state.message }}</p>
              <p v-if="state.detail" class="confirm-detail">{{ state.detail }}</p>
            </div>
          </div>

          <footer class="confirm-actions">
            <button
              ref="cancelButton"
              type="button"
              class="confirm-btn confirm-btn--cancel"
              @click="cancel"
            >
              {{ state.cancelLabel }}
            </button>
            <button
              type="button"
              class="confirm-btn"
              :class="state.tone === 'danger' ? 'confirm-btn--danger' : 'confirm-btn--primary'"
              @click="accept"
            >
              {{ state.confirmLabel }}
            </button>
          </footer>
        </section>
      </div>
    </Transition>
  </AppTeleport>
</template>

<style scoped>
.confirm-backdrop {
  position: fixed;
  z-index: 1200;
  inset: 0;
  display: grid;
  place-items: center;
  padding: 20px;
  background: rgb(16 24 40 / 45%);
  backdrop-filter: blur(1.5px);
}

.confirm-card {
  display: grid;
  width: min(440px, 100%);
  gap: 18px;
  border: 1px solid #e1e8f1;
  border-radius: 10px;
  padding: 20px 22px 18px;
  background: #fff;
  box-shadow: 0 22px 60px rgb(15 30 55 / 28%);
  color: #1f3352;
}

.confirm-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.confirm-head h2 {
  margin: 0;
  color: #1f3352;
  font-size: 19px;
  font-weight: 800;
  letter-spacing: -0.01em;
  line-height: 1.25;
}

.confirm-close {
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

.confirm-close:hover { background: #f0f4f9; color: #526176; }
.confirm-close:focus-visible { outline: 2px solid #304f7e; outline-offset: 1px; }

.confirm-body {
  display: flex;
  align-items: flex-start;
  gap: 14px;
}

.confirm-icon {
  display: inline-grid;
  flex: 0 0 auto;
  width: 38px;
  height: 38px;
  place-items: center;
  border: 2px solid currentColor;
  border-radius: 999px;
  background: #f7f9fc;
}

.confirm-icon--danger { color: #304f7e; }
.confirm-icon--primary { color: #304f7e; }

.confirm-copy { display: grid; gap: 7px; min-width: 0; }

.confirm-copy p { margin: 0; }

#confirm-dialog-message {
  color: #46566d;
  font-size: 14px;
  font-weight: 600;
  line-height: 1.45;
}

.confirm-detail {
  color: #7c8a9e;
  font-size: 12px;
  line-height: 1.5;
}

.confirm-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
}

.confirm-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 102px;
  border: 1px solid transparent;
  border-radius: 7px;
  padding: 9px 16px;
  font-size: 13px;
  font-weight: 750;
  line-height: 1.2;
  cursor: pointer;
  transition: background 0.15s ease, border-color 0.15s ease, box-shadow 0.15s ease;
}

.confirm-btn:focus-visible { outline: 2px solid #304f7e; outline-offset: 2px; }

.confirm-btn--cancel {
  border-color: #d7e0ed;
  background: #fff;
  color: #3b4b63;
}

.confirm-btn--cancel:hover { background: #f5f8fc; border-color: #bccbdd; }

.confirm-btn--danger {
  border-color: #dc4b4b;
  background: #dc4b4b;
  color: #fff;
}

.confirm-btn--danger:hover { border-color: #c53c3c; background: #c53c3c; }

.confirm-btn--primary {
  border-color: #304f7e;
  background: #304f7e;
  color: #fff;
}

.confirm-btn--primary:hover { border-color: #263f66; background: #263f66; }

.confirm-fade-enter-active,
.confirm-fade-leave-active { transition: opacity 0.16s ease; }

.confirm-fade-enter-active .confirm-card,
.confirm-fade-leave-active .confirm-card { transition: transform 0.16s ease, opacity 0.16s ease; }

.confirm-fade-enter-from,
.confirm-fade-leave-to { opacity: 0; }

.confirm-fade-enter-from .confirm-card,
.confirm-fade-leave-to .confirm-card { opacity: 0; transform: translateY(6px) scale(0.985); }

@media (max-width: 480px) {
  .confirm-card { padding: 18px; }
  .confirm-actions { flex-direction: column-reverse; }
  .confirm-btn { width: 100%; }
}

@media (prefers-reduced-motion: reduce) {
  .confirm-fade-enter-active,
  .confirm-fade-leave-active,
  .confirm-fade-enter-active .confirm-card,
  .confirm-fade-leave-active .confirm-card { transition: none; }
}
</style>
