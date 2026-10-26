import { afterEach, describe, expect, it } from "vitest";
import { lockBodyScroll, unlockBodyScroll } from "~/utils/bodyScrollLock";

afterEach(() => {
  document.body.style.overflow = "";
});

describe("bodyScrollLock", () => {
  it("só libera a rolagem quando o último diálogo fecha", () => {
    document.body.style.overflow = "scroll";

    lockBodyScroll();
    lockBodyScroll();
    expect(document.body.style.overflow).toBe("hidden");

    unlockBodyScroll();
    expect(document.body.style.overflow).toBe("hidden");

    unlockBodyScroll();
    expect(document.body.style.overflow).toBe("scroll");
  });
});
