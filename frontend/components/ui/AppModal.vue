<script setup lang="ts">
import { mdiClose } from "@mdi/js";
import { VBtn } from "vuetify/components";
import { nextTick, onBeforeUnmount, onMounted, ref, useId, watch } from "vue";
import { ElDialog } from "element-plus";
import AppTeleport from "~/components/ui/AppTeleport.vue";
import { lockBodyScroll, unlockBodyScroll } from "~/utils/bodyScrollLock";

/**
 * Modal construído sobre o `ElDialog` do Element Plus.
 *
 * O EP entrega overlay, `role="dialog"`, travamento de foco (Tab) e o clique no
 * fundo; o Hub mantém o visual (classes `.modal-*`), o foco no primeiro campo,
 * a restauração do foco anterior, o bloqueio de rolagem e as regras `busy`,
 * `dismissableMask` e `closeOnEscape`.
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
const bodyEl = ref<HTMLElement | null>(null);
const previousFocus = ref<HTMLElement | null>(null);
let scrollLocked = false;
let overlayCleanup: (() => void) | null = null;

const FOCUSABLE =
  'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), ' +
  'textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

function requestClose(): void {
  if (!props.busy) emit("close");
}

/** Escape fecha primeiro um dropdown aberto dentro do modal; depois o modal. */
function onKeydown(event: KeyboardEvent): void {
  if (event.key !== "Escape" || !props.closeOnEscape) return;
  const target = event.target as HTMLElement | null;
  if (target?.closest('[aria-expanded="true"]')) return;
  requestClose();
}

/**
 * Fundo do modal. O fechamento por clique fora do cartão é tratado aqui
 * (mousedown no próprio overlay), como no modal anterior: os eventos de
 * fechamento do ElDialog dependem da transição de saída e não disparam no
 * ambiente de testes; com `close-on-click-modal=false` existe um caminho só.
 */
function bindOverlayMousedown(): void {
  if (overlayCleanup) return;
  const overlay = bodyEl.value?.closest<HTMLElement>(".el-overlay");
  if (!overlay) return;
  const onBackdropMousedown = (event: MouseEvent): void => {
    const target = event.target as HTMLElement;
    if ((target === overlay || target.classList.contains("el-overlay-dialog")) && props.dismissableMask) requestClose();
  };
  overlay.addEventListener("mousedown", onBackdropMousedown);
  overlayCleanup = () => overlay.removeEventListener("mousedown", onBackdropMousedown);
}

function unbindOverlayMousedown(): void {
  overlayCleanup?.();
  overlayCleanup = null;
}

function findFirstField(): HTMLElement | null {
  return (
    bodyEl.value
      ? Array.from(bodyEl.value.querySelectorAll<HTMLElement>(FOCUSABLE)).find(
          (element) => element.tabIndex >= 0 && !element.hidden,
        )
      : null
  ) ?? null;
}

/**
 * O EP devolve o foco ao próprio cartão depois do autofocus interno; quando
 * o foco parar no cartão (abertura ou clique na moldura), devolvemos ao
 * primeiro campo do conteúdo — mesmo comportamento do modal anterior.
 */
function onCardFocusin(event: FocusEvent): void {
  const target = event.target as HTMLElement | null;
  if (target?.classList.contains("modal-card")) findFirstField()?.focus();
}

async function activate(): Promise<void> {
  previousFocus.value = document.activeElement as HTMLElement | null;
  if (!scrollLocked) {
    scrollLocked = true;
    lockBodyScroll();
  }
  await nextTick();
  await nextTick();
  if (!props.open) return;
  bindOverlayMousedown();
  findFirstField()?.focus();
}

function deactivate(): void {
  unbindOverlayMousedown();
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
    void (open ? activate() : deactivate());
  },
  { flush: "post" },
);

onMounted(() => {
  if (props.open) void activate();
});

onBeforeUnmount(() => {
  unbindOverlayMousedown();
  if (scrollLocked) {
    scrollLocked = false;
    unlockBodyScroll();
  }
});
</script>

<template>
  <AppTeleport>
    <!-- `v-if` mantém o contrato "modal fechado = nada no DOM" e o EP recebe
         `model-value` fixo: todo fechamento passa por `requestClose`. -->
    <ElDialog
      v-if="open"
      :model-value="true"
      :title="title"
      class="modal-card"
      :class="{
        'modal-card--wide': size === 'wide',
        'modal-card--contained': contained,
      }"
      :append-to-body="false"
      :lock-scroll="false"
      :show-close="false"
      :close-on-click-modal="false"
      :close-on-press-escape="false"
      footer-class="modal-actions"
      modal-class="app-modal-overlay"
      @keydown="onKeydown"
      @focusin="onCardFocusin"
    >
      <template #header>
        <header class="modal-header">
          <h2 :id="titleId">{{ title }}</h2>
          <VBtn
            type="button"
            variant="text"
            size="x-small"
            aria-label="Fechar"
            data-testid="modal-close"
            :disabled="busy"
            :icon="mdiClose"
            @click="requestClose"
          />
        </header>
      </template>
      <div ref="bodyEl" class="modal-body"><slot /></div>
      <template v-if="$slots.actions" #footer>
        <slot name="actions" />
      </template>
    </ElDialog>
  </AppTeleport>
</template>

<style scoped>
/* ===== Conteúdo do Hub (elementos deste componente) =====
   O re-skin dos elementos internos do ElDialog (overlay, cartão, header,
   body e footer do EP) vive em `assets/css/element-plus.css`, ancorado no
   `modal-class="app-modal-overlay"`: a cadeia Teleport/Transition do
   ElDialog não leva o atributo de escopo, então regras `:deep` não alcançam
   esses elementos. */
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

.modal-body {
  height: 100%;
  min-height: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
  padding: 20px;
}

.modal-card--contained .modal-body {
  overflow: hidden;
  padding-bottom: 0;
}

@media (max-width: 640px) {
  .modal-header { padding: 15px 17px 13px; }
  .modal-body { padding: 16px 20px 20px; }
}
</style>
