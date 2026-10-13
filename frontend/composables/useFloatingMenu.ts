import { onBeforeUnmount, ref, watch, type Ref } from "vue";

const GAP = 4;
const VIEWPORT_MARGIN = 8;
const MAX_HEIGHT = 280;
const MIN_COMFORTABLE = 200;
const MIN_WIDTH = 220;

/**
 * Posiciona um menu (teleportado para o `body`) junto ao campo âncora, com
 * `position: fixed`. Assim ele nunca é recortado por containers com overflow
 * (modais, cards com rolagem) e abre para cima quando falta espaço embaixo.
 */
export function useFloatingMenu(anchor: Ref<HTMLElement | null>, open: Ref<boolean>) {
  const style = ref<Record<string, string>>({});

  function place(): void {
    const element = anchor.value;
    if (!element || typeof window === "undefined") return;
    const rect = element.getBoundingClientRect();
    const viewportHeight = window.innerHeight;
    const viewportWidth = window.innerWidth;
    const below = viewportHeight - rect.bottom - GAP - VIEWPORT_MARGIN;
    const above = rect.top - GAP - VIEWPORT_MARGIN;
    const upward = below < MIN_COMFORTABLE && above > below;
    const width = Math.min(Math.max(rect.width, MIN_WIDTH), viewportWidth - VIEWPORT_MARGIN * 2);
    const left = Math.max(VIEWPORT_MARGIN, Math.min(rect.left, viewportWidth - width - VIEWPORT_MARGIN));
    const maxHeight = Math.max(120, Math.min(MAX_HEIGHT, upward ? above : below));

    style.value = {
      left: `${left}px`,
      width: `${width}px`,
      maxHeight: `${maxHeight}px`,
      ...(upward
        ? { bottom: `${viewportHeight - rect.top + GAP}px` }
        : { top: `${rect.bottom + GAP}px` }),
    };
  }

  function listen(active: boolean): void {
    if (typeof window === "undefined") return;
    const method = active ? "addEventListener" : "removeEventListener";
    // capture: acompanha a rolagem de qualquer ancestral (ex.: corpo do modal).
    window[method]("scroll", place, true);
    window[method]("resize", place);
  }

  watch(open, (isOpen) => {
    if (isOpen) place();
    listen(isOpen);
  });
  onBeforeUnmount(() => listen(false));

  return { style, place };
}
