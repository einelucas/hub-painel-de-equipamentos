import { mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import UploadProgress from "~/components/ui/UploadProgress.vue";

afterEach(() => vi.useRealTimers());

describe("UploadProgress", () => {
  it("counts only server processing time and resets for the next upload", async () => {
    vi.useFakeTimers();
    const wrapper = mount(UploadProgress, { props: { uploading: true, percent: 20, showElapsed: true } });
    await vi.advanceTimersByTimeAsync(10000);
    await wrapper.setProps({ uploading: false });
    expect(wrapper.get(".upload-progress__elapsed").text()).toBe("0s");
    await vi.advanceTimersByTimeAsync(2000);
    expect(wrapper.get(".upload-progress__elapsed").text()).toBe("2s");
    await wrapper.setProps({ uploading: true });
    await wrapper.setProps({ uploading: false });
    expect(wrapper.get(".upload-progress__elapsed").text()).toBe("0s");
    wrapper.unmount();
  });

  it("never presents unknown upload size as zero percent", () => {
    const wrapper = mount(UploadProgress, { props: { uploading: true, percent: null } });
    expect(wrapper.text()).not.toContain("0%");
    expect(wrapper.get("[role='progressbar']").attributes("aria-valuenow")).toBeUndefined();
    wrapper.unmount();
  });
});
