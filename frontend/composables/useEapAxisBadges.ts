import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { eapNameLabel, shortEapLabel } from "~/utils/dashboardAnalytics";

export interface EapAxisTip {
  text: string;
  left: number;
  top: number;
  maxWidth: number;
}

/**
 * Transforma os códigos EAP do eixo Y dos gráficos ApexCharts em badges com o
 * nome completo no balão.
 *
 * O ApexCharts desenha os rótulos como texto SVG, sem suporte a badge: uma
 * pílula `<rect>` é inserida atrás de cada `<text>` depois de cada render.
 * Como os gráficos são recriados/atualizados pelo Apex, a decoração é
 * reagendada pelos eventos `mounted`/`updated` e por resize.
 */
export function useEapAxisBadges(items: () => ReadonlyArray<{ label: string }>) {
  const chartRoot = ref<HTMLElement | null>(null);
  const axisTip = ref<EapAxisTip | null>(null);
  const names = computed(() => {
    const map = new Map<string, string>();
    for (const item of items()) {
      map.set(shortEapLabel(item.label), eapNameLabel(item.label));
    }
    return map;
  });

  let decorateFrame = 0;
  let resizeObserver: ResizeObserver | null = null;

  function decorateYAxisLabels(): void {
    const root = chartRoot.value;
    if (!root) return;
    root.querySelectorAll("rect.eap-axis-badge").forEach((rect) => rect.remove());

    for (const label of root.querySelectorAll<SVGTextElement>("text.apexcharts-yaxis-label")) {
      // O heatmap/barras do Apex desenha o código em um <tspan>; o título
      // nativo (quando existe) é removido para não sobrepor o balão.
      const code = label.querySelector("tspan")?.textContent?.trim()
        || label.getAttribute("data-eap-code")
        || "";
      const name = names.value.get(code);
      if (!name) continue;

      let box: DOMRect;
      try {
        box = label.getBBox();
      } catch {
        continue; // happy-dom/jsdom não implementam getBBox
      }
      if (!box.width) continue;

      const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
      rect.setAttribute("class", "eap-axis-badge");
      rect.setAttribute("x", String(box.x - 6));
      rect.setAttribute("y", String(box.y - 3));
      rect.setAttribute("width", String(box.width + 12));
      rect.setAttribute("height", String(box.height + 6));
      rect.setAttribute("rx", String((box.height + 6) / 2));
      rect.setAttribute("fill", "#eef2f7");
      label.parentNode?.insertBefore(rect, label);

      label.querySelector("title")?.remove();
      label.setAttribute("data-eap-code", code);
      label.setAttribute("data-eap-name", name);
      label.setAttribute("aria-label", name);
      rect.setAttribute("data-eap-name", name);
    }
  }

  /** Espera o ApexCharts concluir o desenho antes de medir os rótulos. */
  function scheduleDecoration(): void {
    if (typeof window === "undefined") return;
    window.cancelAnimationFrame(decorateFrame);
    decorateFrame = window.requestAnimationFrame(() => {
      decorateFrame = window.requestAnimationFrame(decorateYAxisLabels);
    });
  }

  function showAxisTip(event: MouseEvent): void {
    const target = event.target as Element | null;
    const label = target?.closest("[data-eap-name]");
    const name = label?.getAttribute("data-eap-name");
    if (!label || !name || typeof window === "undefined") return;

    const box = label.getBoundingClientRect();
    const left = box.right + 10;
    axisTip.value = {
      text: name,
      left,
      top: box.top + box.height / 2,
      maxWidth: Math.min(420, Math.max(160, window.innerWidth - left - 12)),
    };
  }

  function hideAxisTip(event: MouseEvent): void {
    const target = event.target as Element | null;
    if (!target?.closest("[data-eap-name]")) return;
    // Trocar entre a pílula e o texto não deve piscar o balão.
    if ((event.relatedTarget as Element | null)?.closest("[data-eap-name]")) return;
    axisTip.value = null;
  }

  function clearAxisTip(): void {
    axisTip.value = null;
  }

  function observeRoot(): void {
    resizeObserver?.disconnect();
    if (typeof ResizeObserver === "undefined" || !chartRoot.value) return;
    resizeObserver = new ResizeObserver(scheduleDecoration);
    resizeObserver.observe(chartRoot.value);
  }

  onMounted(() => {
    window.addEventListener("resize", scheduleDecoration);
    window.addEventListener("scroll", clearAxisTip, true);
    observeRoot();
    if (document.fonts) void document.fonts.ready.then(scheduleDecoration);
    scheduleDecoration();
  });

  // O gráfico só entra no DOM depois do carregamento; observa quando aparecer.
  watch(chartRoot, observeRoot, { flush: "post" });

  onBeforeUnmount(() => {
    window.removeEventListener("resize", scheduleDecoration);
    window.removeEventListener("scroll", clearAxisTip, true);
    resizeObserver?.disconnect();
    window.cancelAnimationFrame(decorateFrame);
  });

  const chartEvents = {
    mounted: scheduleDecoration,
    updated: scheduleDecoration,
  };

  return { chartRoot, axisTip, chartEvents, showAxisTip, hideAxisTip };
}
