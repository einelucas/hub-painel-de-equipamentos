import { mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import SupplierImportModal from "~/components/supplier/SupplierImportModal.vue";

async function settle(wrapper: ReturnType<typeof mount>) {
  for (let i = 0; i < 3; i += 1) {
    await new Promise((resolve) => setTimeout(resolve));
    await wrapper.vm.$nextTick();
  }
}

function mountModal(upload: ReturnType<typeof vi.fn>) {
  vi.stubGlobal("useApi", () => ({ upload }));
  return mount(SupplierImportModal, { props: { open: true } });
}

async function mountSettledModal(upload: ReturnType<typeof vi.fn>) {
  const wrapper = mountModal(upload);
  // O ElDialog renderiza o conteúdo um tick depois de abrir (padrão EP).
  await settle(wrapper);
  return wrapper;
}

async function pickFile(wrapper: ReturnType<typeof mount>) {
  const file = new File(["x"], "fornecedores.xlsx");
  const input = wrapper.get("[data-testid='supplier-import-file']");
  Object.defineProperty(input.element, "files", { value: [file], configurable: true });
  await input.trigger("change");
  return file;
}

afterEach(() => vi.unstubAllGlobals());

describe("SupplierImportModal", () => {
  it("mantém o envio desabilitado sem arquivo e envia a planilha via POST", async () => {
    const result = { total: 3, created: 1, updated: 1, unchanged: 0, errors: [{ row: 4, message: "Documento inválido" }] };
    const upload = vi.fn().mockResolvedValue(result);
    const wrapper = await mountSettledModal(upload);

    expect(wrapper.get("[data-testid='supplier-import-submit']").attributes("disabled")).toBeDefined();
    const file = await pickFile(wrapper);
    await wrapper.get("form").trigger("submit");
    await settle(wrapper);

    expect(upload).toHaveBeenCalledTimes(1);
    const [path, form, method] = upload.mock.calls[0]!;
    expect(path).toBe("/suppliers/import");
    expect(method).toBe("POST");
    expect((form as FormData).get("file")).toBeInstanceOf(File);
    expect(((form as FormData).get("file") as File).name).toBe(file.name);
    expect(wrapper.emitted("imported")?.[0]).toEqual([result]);

    const summary = wrapper.get("[data-testid='supplier-import-result']").text();
    expect(summary).toContain("1 criado(s)");
    expect(summary).toContain("1 atualizado(s)");
    expect(summary).toContain("0 sem alteração");
    expect(summary).toContain("1 erro(s)");
    expect(wrapper.get("[data-testid='supplier-import-errors']").text()).toContain("Linha 4: Documento inválido");
  });

  it("mostra a mensagem do servidor quando a importação falha", async () => {
    const upload = vi.fn().mockRejectedValue(new Error("Colunas obrigatórias ausentes."));
    const wrapper = await mountSettledModal(upload);
    await pickFile(wrapper);
    await wrapper.get("form").trigger("submit");
    await settle(wrapper);

    expect(wrapper.get("[role='alert']").text()).toBe("Colunas obrigatórias ausentes.");
    expect(wrapper.emitted("imported")).toBeUndefined();
  });

  it("mostra progresso do envio, depois processamento com contador de tempo", async () => {
    vi.useFakeTimers();
    try {
      let onProgress: (loaded: number, total: number) => void = () => {};
      let finish: (value: unknown) => void = () => {};
      const upload = vi.fn((_p: string, _f: FormData, _m: string, cb: (l: number, t: number) => void) => {
        onProgress = cb;
        return new Promise((resolve) => { finish = resolve; });
      });
      const wrapper = mountModal(upload as unknown as ReturnType<typeof vi.fn>);
      // Fake timers: settle() usa setTimeout e travaria; nextTick é microtask.
      await wrapper.vm.$nextTick();
      await wrapper.vm.$nextTick();
      await pickFile(wrapper);
      expect(wrapper.get("[data-testid='supplier-import-file-info']").text()).toContain("fornecedores.xlsx");
      await wrapper.get("form").trigger("submit");

      onProgress(50, 100);
      await wrapper.vm.$nextTick();
      expect(wrapper.get("[role='progressbar']").attributes("aria-valuenow")).toBe("50");
      expect(wrapper.get("[data-testid='supplier-import-progress-status']").text()).toContain("50%");
      expect(wrapper.get("form").attributes("aria-busy")).toBe("true");
      expect(wrapper.get("[data-testid='supplier-import-submit']").attributes("disabled")).toBeDefined();

      wrapper.findComponent({ name: "AppModal" }).vm.$emit("close");
      expect(wrapper.emitted("close")).toBeUndefined();

      onProgress(100, 100);
      await wrapper.vm.$nextTick();
      expect(wrapper.get("[data-testid='supplier-import-progress-status']").text()).toContain("Processando planilha no servidor");
      expect(wrapper.get("[role='progressbar']").attributes("aria-valuenow")).toBeUndefined();

      vi.advanceTimersByTime(12000);
      await wrapper.vm.$nextTick();
      expect(wrapper.get("[data-testid='supplier-import-progress-elapsed']").text()).toBe("12s");

      finish({ total: 0, created: 0, updated: 0, unchanged: 0, errors: [] });
      await vi.runAllTimersAsync();
      expect(wrapper.find("[data-testid='supplier-import-progress']").exists()).toBe(false);
      expect(wrapper.find("[data-testid='supplier-import-result']").exists()).toBe(true);
    } finally {
      vi.useRealTimers();
    }
  });
});
