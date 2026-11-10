export interface ReportCaptureOptions {
  scale?: number;
  backgroundColor?: string;
}

interface ChartReplacement {
  original: HTMLElement;
  image: HTMLImageElement;
}

function cssChannel(value: string): number {
  const parsed = Number.parseFloat(value);
  if (!Number.isFinite(parsed)) return 0;
  const normalized = value.endsWith("%") ? parsed / 100 : parsed;
  return Math.round(Math.min(1, Math.max(0, normalized)) * 255);
}

/** Chrome pode expor cores calculadas como `color(srgb ...)` ou
 * `color(display-p3 ...)`. O parser do html2canvas ainda não aceita essa
 * sintaxe, então a convertemos para rgba somente dentro do clone capturado. */
export function normalizeUnsupportedColorFunctions(value: string): string {
  return value.replace(
    /color\(\s*(?:srgb|display-p3)\s+([+-]?(?:\d*\.)?\d+%?)\s+([+-]?(?:\d*\.)?\d+%?)\s+([+-]?(?:\d*\.)?\d+%?)(?:\s*\/\s*([+-]?(?:\d*\.)?\d+%?))?\s*\)/gi,
    (_match, red: string, green: string, blue: string, alpha?: string) => {
      const opacity = alpha === undefined
        ? 1
        : Math.min(1, Math.max(0, Number.parseFloat(alpha) / (alpha.endsWith("%") ? 100 : 1)));
      return `rgba(${cssChannel(red)}, ${cssChannel(green)}, ${cssChannel(blue)}, ${opacity})`;
    },
  );
}

export function sanitizeReportCloneColors(root: HTMLElement): void {
  const elements = [root, ...Array.from(root.querySelectorAll<HTMLElement>("*"))];
  for (const element of elements) {
    const computed = getComputedStyle(element);
    for (let index = 0; index < computed.length; index += 1) {
      const property = computed.item(index);
      const value = computed.getPropertyValue(property);
      if (!value.toLowerCase().includes("color(")) continue;
      const normalized = normalizeUnsupportedColorFunctions(value);
      if (normalized !== value) element.style.setProperty(property, normalized, "important");
    }
  }
}

function nextFrame(): Promise<void> {
  return new Promise((resolve) => requestAnimationFrame(() => resolve()));
}

async function decodeImage(image: HTMLImageElement): Promise<void> {
  if (image.complete && image.naturalWidth > 0) return;
  if (typeof image.decode === "function") {
    await image.decode();
    return;
  }
  await new Promise<void>((resolve, reject) => {
    image.addEventListener("load", () => resolve(), { once: true });
    image.addEventListener("error", () => reject(new Error("Falha ao carregar imagem do report.")), {
      once: true,
    });
  });
}

/** Espera fontes, logos e dois ciclos de layout. Isso evita capturar o
 * skeleton do ClientOnly ou dimensões intermediárias do Vuetify/ApexCharts. */
export async function waitForReportAssets(root: HTMLElement): Promise<void> {
  if (document.fonts?.ready) await document.fonts.ready;
  const expectedCharts = root.querySelectorAll(".report-chart").length;
  for (let attempt = 0; attempt < 120 && expectedCharts > 0; attempt += 1) {
    if (root.querySelectorAll(".apexcharts-canvas svg").length >= expectedCharts) break;
    await nextFrame();
  }
  if (root.querySelectorAll(".apexcharts-canvas svg").length < expectedCharts) {
    throw new Error("Os gráficos ainda não terminaram de renderizar.");
  }
  await Promise.all(
    Array.from(root.querySelectorAll<HTMLImageElement>("img")).map((image) =>
      decodeImage(image),
    ),
  );
  await nextFrame();
  await nextFrame();
}

function serializedSvg(svg: SVGSVGElement, width: number, height: number): string {
  const clone = svg.cloneNode(true) as SVGSVGElement;
  clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  clone.setAttribute("width", String(width));
  clone.setAttribute("height", String(height));
  clone.setAttribute("viewBox", clone.getAttribute("viewBox") || `0 0 ${width} ${height}`);
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(
    new XMLSerializer().serializeToString(clone),
  )}`;
}

/** html2canvas não rasteriza de forma consistente o SVG dinâmico do Apex em
 * todos os navegadores. Durante a captura cada gráfico vira uma imagem SVG
 * estática, com as mesmas dimensões, e é restaurado no final. */
export async function rasterizeApexCharts(root: HTMLElement): Promise<() => void> {
  const replacements: ChartReplacement[] = [];
  const charts = Array.from(root.querySelectorAll<HTMLElement>(".apexcharts-canvas"));

  try {
    for (const chart of charts) {
      const svg = chart.querySelector<SVGSVGElement>("svg.apexcharts-svg, svg");
      if (!svg) continue;
      const rect = chart.getBoundingClientRect();
      const width = Math.max(1, Math.round(rect.width || Number(svg.getAttribute("width")) || 1));
      const height = Math.max(1, Math.round(rect.height || Number(svg.getAttribute("height")) || 1));
      const image = document.createElement("img");
      image.className = "report-apex-snapshot";
      image.alt = chart.getAttribute("aria-label") || "Gráfico do relatório";
      image.width = width;
      image.height = height;
      image.style.display = "block";
      image.style.width = `${width}px`;
      image.style.height = `${height}px`;
      image.style.maxWidth = "100%";
      image.src = serializedSvg(svg, width, height);
      await decodeImage(image);
      chart.replaceWith(image);
      replacements.push({ original: chart, image });
    }
  } catch (error) {
    for (const { original, image } of replacements.reverse()) {
      if (image.isConnected) image.replaceWith(original);
    }
    throw error;
  }

  return () => {
    for (const { original, image } of replacements.reverse()) {
      if (image.isConnected) image.replaceWith(original);
    }
  };
}

export async function captureReportElement(
  element: HTMLElement,
  options: ReportCaptureOptions = {},
): Promise<HTMLCanvasElement> {
  await waitForReportAssets(element);
  const restoreCharts = await rasterizeApexCharts(element);
  const previousCaptureTarget = element.dataset.reportCaptureTarget;
  element.dataset.reportCaptureTarget = "true";
  try {
    const { default: html2canvas } = await import("html2canvas");
    return await html2canvas(element, {
      scale: options.scale ?? 2,
      backgroundColor: options.backgroundColor ?? "#ffffff",
      useCORS: true,
      allowTaint: false,
      foreignObjectRendering: false,
      logging: false,
      scrollX: 0,
      scrollY: 0,
      // O clone precisa ter ao menos o tamanho da página A4 fixa. Em telas
      // estreitas isso impede media queries/mobile de alterarem o relatório.
      windowWidth: Math.max(document.documentElement.clientWidth, element.scrollWidth),
      windowHeight: Math.max(document.documentElement.clientHeight, element.scrollHeight),
      removeContainer: true,
      onclone: (clonedDocument) => {
        const clonedElement = clonedDocument.querySelector<HTMLElement>(
          `[data-report-capture-target="${element.dataset.reportCaptureTarget}"]`,
        );
        if (clonedElement) sanitizeReportCloneColors(clonedElement);
        const style = clonedDocument.createElement("style");
        style.dataset.reportCapture = "true";
        style.textContent = `
          *, *::before, *::after {
            animation: none !important;
            caret-color: transparent !important;
            transition: none !important;
          }
          .report-page { box-shadow: none !important; transform: none !important; }
          .v-ripple__container, .apexcharts-tooltip, .apexcharts-toolbar { display: none !important; }
          .report-apex-snapshot { opacity: 1 !important; visibility: visible !important; }
        `;
        clonedDocument.head.appendChild(style);
      },
    });
  } finally {
    if (previousCaptureTarget === undefined) delete element.dataset.reportCaptureTarget;
    else element.dataset.reportCaptureTarget = previousCaptureTarget;
    restoreCharts();
  }
}

export function stitchReportCanvases(canvases: HTMLCanvasElement[]): HTMLCanvasElement {
  if (!canvases.length) throw new Error("Nenhuma página disponível para exportação.");
  const width = Math.max(...canvases.map((canvas) => canvas.width));
  const height = canvases.reduce((sum, canvas) => sum + canvas.height, 0);
  const result = document.createElement("canvas");
  result.width = width;
  result.height = height;
  const context = result.getContext("2d");
  if (!context) throw new Error("O navegador não oferece suporte à exportação de PNG.");
  context.fillStyle = "#ffffff";
  context.fillRect(0, 0, width, height);
  let offset = 0;
  for (const canvas of canvases) {
    context.drawImage(canvas, 0, offset);
    offset += canvas.height;
  }
  return result;
}
