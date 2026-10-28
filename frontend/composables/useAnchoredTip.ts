import { onBeforeUnmount, ref } from "vue";

/** Respiro entre o badge e o balão. */
const GAP = 9;
/** Respiro entre o balão e a borda da viewport. */
const VIEWPORT_MARGIN = 8;
/** Folga para a seta não encostar nos cantos arredondados do balão. */
const ARROW_MARGIN = 14;

/**
 * Ancora um balão de ajuda ao elemento que o abre, com `position: fixed`.
 *
 * O balão continua dentro do badge — o texto segue acessível a leitores de
 * tela e a quem inspeciona o DOM — mas é posicionado pela viewport. Dentro de
 * uma tabela com `overflow`, um balão `absolute` era recortado e a lista
 * completa (ex.: os work packages escondidos atrás do "+7") não aparecia.
 */
export function useAnchoredTip() {
  const trigger = ref<HTMLElement | null>(null);
  const tip = ref<HTMLElement | null>(null);
  const open = ref(false);
  /** `true` quando o balão abre acima do badge, que é o caso normal. */
  const above = ref(true);
  const style = ref<Record<string, string>>({});

  function place(): void {
    const element = trigger.value;
    const bubble = tip.value;
    if (!element || !bubble || typeof window === "undefined") return;

    const rect = element.getBoundingClientRect();
    const width = bubble.offsetWidth;
    const height = bubble.offsetHeight;
    const half = width / 2;

    // Centralizado no badge, mas sempre dentro da tela.
    const center = rect.left + rect.width / 2;
    const left = Math.min(
      Math.max(center, VIEWPORT_MARGIN + half),
      Math.max(VIEWPORT_MARGIN + half, window.innerWidth - VIEWPORT_MARGIN - half),
    );

    // Abre acima; sem espaço (primeira linha da tabela), abre abaixo.
    const upward = rect.top - GAP - height - VIEWPORT_MARGIN >= 0;
    above.value = upward;

    // A seta acompanha o centro do badge mesmo quando o balão é deslocado.
    const arrow = Math.min(
      Math.max(center - (left - half), ARROW_MARGIN),
      Math.max(ARROW_MARGIN, width - ARROW_MARGIN),
    );

    style.value = {
      // `left` acima representa o centro desejado; CSS posiciona pela borda
      // esquerda. Compensar metade da largura mantém o balão sobre o badge.
      left: `${left - half}px`,
      "--tip-arrow": `${arrow}px`,
      ...(upward
        ? { bottom: `${window.innerHeight - rect.top + GAP}px` }
        : { top: `${rect.bottom + GAP}px` }),
    };
  }

  function listen(active: boolean): void {
    if (typeof window === "undefined") return;
    const method = active ? "addEventListener" : "removeEventListener";
    // capture: acompanha a rolagem de qualquer ancestral (ex.: corpo da tabela).
    window[method]("scroll", place, true);
    window[method]("resize", place);
  }

  function show(): void {
    place();
    open.value = true;
    listen(true);
  }

  function hide(): void {
    open.value = false;
    listen(false);
  }

  onBeforeUnmount(() => listen(false));

  return { trigger, tip, open, above, style, show, hide };
}
