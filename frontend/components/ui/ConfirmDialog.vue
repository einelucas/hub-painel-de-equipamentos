<script setup lang="ts">
import Button from "~/components/ui/Button.vue";
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue";
import { AlertTriangle, Info, Trash2, X } from "lucide-vue-next";
import AppTeleport from "~/components/ui/AppTeleport.vue";
import { useConfirm } from "~/composables/useConfirm";
import { lockBodyScroll, unlockBodyScroll } from "~/utils/bodyScrollLock";

/**
 * Confirmação global com ações nativas do Element Plus.
 */
const { state, accept, cancel } = useConfirm();
const CONFIRMATION_Z_INDEX = 10_000;

const card = ref<HTMLElement | null>(null);
const cancelButton = ref<InstanceType<typeof Button> | null>(null);
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
      (cancelButton.value?.$el as HTMLButtonElement | undefined)?.focus();
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
      <div
        v-if="state.open"
        class="confirm-backdrop"
        :style="{ zIndex: CONFIRMATION_Z_INDEX }"
        @mousedown.self="cancel"
      >
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
            <Button type="button" class="confirm-close" aria-label="Fechar" variant="ghost" size="icon-sm" @click="cancel">
              <X :size="20" aria-hidden="true" />
            </Button>
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
            <Button
              ref="cancelButton"
              type="button"
              class="confirm-btn confirm-btn--cancel"
              variant="outline"
              @click="cancel"
            >
              {{ state.cancelLabel }}
            </Button>
            <Button
              type="button"
              class="confirm-btn"
              :class="state.tone === 'danger' ? 'confirm-btn--danger' : 'confirm-btn--primary'"
              :variant="state.tone === 'danger' ? 'destructive' : 'default'"
              @click="accept"
            >
              {{ state.confirmLabel }}
            </Button>
          </footer>
        </section>
      </div>
    </Transition>
  </AppTeleport>
</template>

<style scoped>
.confirm-backdrop {
  position: fixed;
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
}

@media (prefers-reduced-motion: reduce) {
  .confirm-fade-enter-active,
  .confirm-fade-leave-active,
  .confirm-fade-enter-active .confirm-card,
  .confirm-fade-leave-active .confirm-card { transition: none; }
}
</style>
