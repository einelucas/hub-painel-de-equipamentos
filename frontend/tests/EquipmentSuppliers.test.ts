import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import EquipmentSuppliers from "~/components/equipment/EquipmentSuppliers.vue";
import { useConfirm } from "~/composables/useConfirm";
import type { EquipmentSupplier, Supplier } from "~/types/equipment";
import { menuOptions, openMenu } from "./support/searchableSelect";

function supplier(id: string, legalName: string, isPrimary: boolean): EquipmentSupplier {
  return {
    id: `link-${id}`,
    supplier: {
      id,
      legalName,
      tradeName: null,
      taxId: null,
      active: true,
      createdAt: "2026-09-20T00:00:00",
      updatedAt: "2026-09-20T00:00:00",
    },
    role: isPrimary ? "Fabricante" : null,
    isPrimary,
    startStage: 1,
    endStage: null,
    startedAt: "2026-09-20T00:00:00",
    endedAt: null,
    changeReason: null,
    source: "MANUAL",
    changedByUserId: "user-1",
    createdAt: "2026-09-20T00:00:00",
  };
}

const passthrough = { template: "<div><slot /></div>" };

function mountWith(
  items: EquipmentSupplier[],
  can: (permission: string) => boolean,
  catalogRequest?: Promise<{ items: Supplier[] }>,
) {
  const catalog: Supplier[] = items.map((item) => item.supplier).concat({
    id: "s-2",
    legalName: "Secundária SA",
    tradeName: null,
    taxId: null,
    active: true,
    createdAt: "2026-09-20T00:00:00",
    updatedAt: "2026-09-20T00:00:00",
  });
  const get = vi.fn((path: string) =>
    path === "/suppliers"
      ? (catalogRequest ?? Promise.resolve({ items: catalog }))
      : Promise.resolve({ items }),
  );
  const patch = vi.fn().mockResolvedValue({});
  const put = vi.fn().mockResolvedValue({});
  const del = vi.fn().mockResolvedValue({});
  vi.stubGlobal("useApi", () => ({ get, patch, put, post: vi.fn(), delete: del }));
  vi.stubGlobal("useAuthStore", () => ({ can }));
  vi.stubGlobal("onMounted", (fn: () => void) => fn());

  const wrapper = mount(EquipmentSuppliers, {
    props: { equipmentId: "eq-1" },
    global: {
      stubs: {
        Table: passthrough,
        TableHeader: passthrough,
        TableRow: passthrough,
        TableHead: passthrough,
        TableBody: passthrough,
        TableCell: passthrough,
        AppModal: {
          props: ["open", "title"],
          template: "<div v-if='open' class='modal'><h2>{{ title }}</h2><slot /></div>",
        },
        NuxtLink: { props: ["to"], template: "<a :href='to'><slot /></a>" },
      },
    },
  });
  return { wrapper, get, patch, put, del };
}

describe("EquipmentSuppliers", () => {
  afterEach(() => useConfirm().cancel());

  it("mostra o spinner antes de abrir o modal enquanto o catálogo carrega", async () => {
    let resolveCatalog!: (value: { items: Supplier[] }) => void;
    const catalogRequest = new Promise<{ items: Supplier[] }>((resolve) => {
      resolveCatalog = resolve;
    });
    const { wrapper } = mountWith([], () => true, catalogRequest);

    const linkButton = wrapper
      .findAll("button")
      .find((item) => item.text().includes("Vincular fornecedor"))!;
    await linkButton.trigger("click");

    expect(linkButton.attributes("aria-busy")).toBe("true");
    expect(wrapper.find(".modal").exists()).toBe(false);
    await vi.waitFor(() => {
      expect(wrapper.get(".modal h2").text()).toBe("Vincular fornecedor");
    });
    expect(wrapper.get(".catalog-loading").text()).toContain("Carregando fornecedores");

    resolveCatalog({
      items: [supplier("s-1", "Fornecedor disponível", true).supplier],
    });
    await flushPromises();

    expect(wrapper.find(".catalog-loading").exists()).toBe(false);
  });

  it("lista o único fornecedor vinculado (Etapa 7A: no máximo um por equipamento)", async () => {
    const { wrapper } = mountWith([supplier("s-1", "Principal SA", true)], () => true);
    await new Promise((resolve) => setTimeout(resolve));
    await wrapper.vm.$nextTick();

    expect(wrapper.text()).toContain("Principal SA");
    const current = wrapper.get("[data-testid='current-supplier']");
    expect(current.text()).toContain("Principal SA");
    expect(current.text()).toContain("Vínculo ativo");
    expect(current.text()).toContain("Vinculado desde");
    expect(current.text()).toContain("Fase de entrada");
    expect(current.text()).toContain("Papel");
    expect(wrapper.find("[data-testid='replace-supplier']").exists()).toBe(true);
  });

  it("pede confirmação e alerta sobre as consequências antes de encerrar", async () => {
    const link = supplier("s-1", "Principal SA", true);
    const { wrapper, del } = mountWith([link], () => true);
    await flushPromises();

    await wrapper.get("[data-testid='unlink-supplier']").trigger("click");

    expect(del).not.toHaveBeenCalled();
    expect(useConfirm().state.open).toBe(true);
    expect(useConfirm().state.title).toBe("Encerrar vínculo");
    expect(useConfirm().state.message).toContain("Principal SA");
    expect(useConfirm().state.detail).toContain("ficará sem fornecedor ativo");
    expect(useConfirm().state.icon).toBe("warning");

    useConfirm().cancel();
    await flushPromises();
    expect(del).not.toHaveBeenCalled();

    await wrapper.get("[data-testid='unlink-supplier']").trigger("click");
    useConfirm().accept();
    await flushPromises();

    expect(del).toHaveBeenCalledWith("/equipments/eq-1/suppliers/s-1");
  });

  it("permite substituir o fornecedor vinculado (PUT, não outro POST)", async () => {
    const { wrapper, put } = mountWith([supplier("s-1", "Principal SA", true)], () => true);
    await new Promise((resolve) => setTimeout(resolve));
    await wrapper.vm.$nextTick();

    await wrapper.get("[data-testid='replace-supplier']").trigger("click");
    await vi.waitFor(() => {
      expect(wrapper.find("[data-testid='supplier-link-combobox']").exists()).toBe(true);
    });
    await openMenu(wrapper, "supplier-link-combobox");
    const replacement = menuOptions(wrapper, "supplier-link-combobox").find((option) =>
      option.text().includes("Secundária SA"),
    );
    expect(replacement).toBeDefined();
    await replacement!.trigger("click");
    await wrapper.get("form").trigger("submit");

    expect(put).toHaveBeenCalledWith("/equipments/eq-1/suppliers", {
      supplierId: "s-2",
      role: null,
      changeReason: null,
      isPrimary: true,
    });
  });

  it("esconde as ações de escrita de quem não tem suppliers:write", async () => {
    const { wrapper } = mountWith(
      [supplier("s-1", "Principal SA", true)],
      (permission) => permission !== "suppliers:write",
    );
    await new Promise((resolve) => setTimeout(resolve));
    await wrapper.vm.$nextTick();

    expect(wrapper.text()).not.toContain("Vincular fornecedor");
    expect(wrapper.text()).not.toContain("Encerrar vínculo");
  });

  it("mostra estado vazio sem bloquear o processo", async () => {
    const { wrapper } = mountWith([], () => true);
    await new Promise((resolve) => setTimeout(resolve));
    await wrapper.vm.$nextTick();

    expect(wrapper.get("[data-testid='suppliers-empty']").text()).toContain(
      "Nenhum fornecedor vinculado",
    );
  });

  it("separa o fornecedor atual do histórico encerrado", async () => {
    const old = supplier("s-old", "Fornecedor Anterior", false);
    old.endStage = 4;
    old.endedAt = "2026-10-01T00:00:00";
    old.changeReason = "Nova contratação";
    const { wrapper } = mountWith(
      [supplier("s-1", "Fornecedor Atual", true), old],
      () => true,
    );
    await new Promise((resolve) => setTimeout(resolve));
    await wrapper.vm.$nextTick();

    expect(wrapper.get("[data-testid='current-supplier']").text()).toContain("Fornecedor Atual");
    expect(wrapper.get("[data-testid='supplier-history']").text()).toContain("Fornecedor Anterior");
    expect(wrapper.get("[data-testid='supplier-history']").text()).toContain("Nova contratação");
  });
});
