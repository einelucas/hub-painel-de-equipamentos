import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  captureReportElement,
  rasterizeApexCharts,
  stitchReportCanvases,
} from "~/utils/reportCapture";

const html2canvasMock = vi.hoisted(() => vi.fn());

vi.mock("html2canvas", () => ({ default: html2canvasMock }));

describe("reportCapture", () => {
  beforeEach(() => {
    html2canvasMock.mockReset();
    document.body.innerHTML = "";
  });

  it("passes valid html2canvas options without replacing its canvas option", async () => {
    const root = document.createElement("div");
    root.className = "report-page";
    document.body.appendChild(root);
    const result = document.createElement("canvas");
    html2canvasMock.mockResolvedValue(result);

    await expect(captureReportElement(root, { scale: 1.5 })).resolves.toBe(result);

    expect(html2canvasMock).toHaveBeenCalledOnce();
    const options = html2canvasMock.mock.calls[0]?.[1];
    expect(options).toMatchObject({
      scale: 1.5,
      useCORS: true,
      allowTaint: false,
      foreignObjectRendering: false,
    });
    expect(options).not.toHaveProperty("canvas");
  });

  it("replaces ApexCharts SVGs with images during capture and restores them", async () => {
    const decode = vi
      .spyOn(HTMLImageElement.prototype, "decode")
      .mockResolvedValue(undefined);
    const root = document.createElement("div");
    root.innerHTML = `
      <div class="apexcharts-canvas" aria-label="Pipeline">
        <svg class="apexcharts-svg" width="320" height="180" viewBox="0 0 320 180">
          <rect width="320" height="180" fill="#304f7e" />
        </svg>
      </div>
    `;
    document.body.appendChild(root);
    const chart = root.querySelector<HTMLElement>(".apexcharts-canvas")!;
    chart.getBoundingClientRect = () =>
      ({ width: 320, height: 180 }) as DOMRect;

    const restore = await rasterizeApexCharts(root);

    const snapshot = root.querySelector<HTMLImageElement>(".report-apex-snapshot");
    expect(snapshot?.alt).toBe("Pipeline");
    expect(snapshot?.src).toContain("data:image/svg+xml");
    expect(root.contains(chart)).toBe(false);

    restore();
    expect(root.contains(chart)).toBe(true);
    expect(root.querySelector(".report-apex-snapshot")).toBeNull();
    decode.mockRestore();
  });

  it("stitches captured report pages into a real canvas", () => {
    const context = {
      fillStyle: "",
      fillRect: vi.fn(),
      drawImage: vi.fn(),
    };
    const getContext = vi
      .spyOn(HTMLCanvasElement.prototype, "getContext")
      .mockReturnValue(context as unknown as CanvasRenderingContext2D);
    const first = document.createElement("canvas");
    first.width = 600;
    first.height = 800;
    const second = document.createElement("canvas");
    second.width = 600;
    second.height = 900;

    const result = stitchReportCanvases([first, second]);

    expect(result).toBeInstanceOf(HTMLCanvasElement);
    expect(result.width).toBe(600);
    expect(result.height).toBe(1700);
    expect(context.drawImage).toHaveBeenNthCalledWith(1, first, 0, 0);
    expect(context.drawImage).toHaveBeenNthCalledWith(2, second, 0, 800);
    getContext.mockRestore();
  });
});
