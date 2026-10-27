import type { Component } from "vue";
import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import type { AdminUser } from "~/types/api";

let UsersPage: Component;

const users: AdminUser[] = [
  {
    id: "user-1",
    name: "Lucas Pinheiro",
    email: "lucas.pinheiro@example.com",
    role: "ADMIN",
    active: true,
    authProvider: "LOCAL",
    lastLoginAt: null,
    createdAt: "2026-10-16T00:00:00Z",
  },
  {
    id: "user-2",
    name: "Diego Costa",
    email: "diego.costa@example.com",
    role: "ANALYST",
    active: true,
    authProvider: "LOCAL",
    lastLoginAt: "2026-10-16T12:00:00Z",
    createdAt: "2026-10-16T00:00:00Z",
  },
];

beforeAll(async () => {
  vi.stubGlobal("definePageMeta", vi.fn());
  UsersPage = (await import("~/pages/usuarios.vue")).default;
});

afterEach(() => {
  vi.unstubAllGlobals();
  // `definePageMeta` permanece disponível porque o setup da página roda a
  // cada mount, embora o módulo Vue seja importado apenas uma vez.
  vi.stubGlobal("definePageMeta", vi.fn());
});

function mountPage() {
  const get = vi.fn().mockResolvedValue({ items: structuredClone(users) });
  const post = vi.fn().mockResolvedValue({
    user: { id: "user-3", name: "Ana Souza", email: "ana@example.com", role: "VIEWER", active: true },
  });
  const patch = vi.fn().mockImplementation((_path: string, changes: Partial<AdminUser>) =>
    Promise.resolve({ user: { ...users[1], ...changes } }),
  );
  vi.stubGlobal("useApi", () => ({ get, post, patch }));
  vi.stubGlobal("useAuthStore", () => ({ user: { id: "user-1", role: "ADMIN" } }));

  const passthrough = { template: "<div><slot /></div>" };
  const wrapper = mount(UsersPage, {
    global: {
      stubs: {
        ModuleWorkspace: passthrough,
        AppModal: {
          props: ["open", "title"],
          template: "<div v-if='open'><h2>{{ title }}</h2><slot /><slot name='actions' /></div>",
        },
        Table: { template: "<table><slot /></table>" },
        TableHeader: { template: "<thead><slot /></thead>" },
        TableBody: { template: "<tbody><slot /></tbody>" },
        TableRow: { template: "<tr><slot /></tr>" },
        TableHead: { template: "<th><slot /></th>" },
        TableCell: { template: "<td><slot /></td>" },
      },
    },
  });
  return { wrapper, get, post, patch };
}

describe("página temporária de usuários", () => {
  it("lista usuários e deixa claro que a rota é temporária", async () => {
    const { wrapper, get } = mountPage();
    await flushPromises();

    expect(get).toHaveBeenCalledWith("/usuarios");
    expect(wrapper.text()).toContain("Página temporária e não listada no menu");
    expect(wrapper.text()).toContain("lucas.pinheiro@example.com");
    expect(wrapper.text()).toContain("diego.costa@example.com");
  });

  it("cria usuário com nome, e-mail e perfil", async () => {
    const { wrapper, post, get } = mountPage();
    await flushPromises();
    await wrapper.get("[data-testid='new-user']").trigger("click");

    const form = wrapper.get("#create-user-form");
    const inputs = form.findAll("input");
    await inputs[0]!.setValue("Ana Souza");
    await inputs[1]!.setValue("ana@example.com");
    await form.get("select").setValue("VIEWER");
    await form.trigger("submit");
    await flushPromises();

    expect(post).toHaveBeenCalledWith("/usuarios", {
      name: "Ana Souza",
      email: "ana@example.com",
      role: "VIEWER",
    });
    expect(get).toHaveBeenCalledTimes(2);
    expect(wrapper.text()).toContain("deverá alterá-la no primeiro acesso");
  });

  it("altera o perfil de outra conta sem liberar a própria conta", async () => {
    const { wrapper, patch } = mountPage();
    await flushPromises();

    const ownSelect = wrapper.get("[aria-label='Perfil de Lucas Pinheiro']");
    expect((ownSelect.element as HTMLSelectElement).disabled).toBe(true);
    await wrapper.get("[aria-label='Perfil de Diego Costa']").setValue("ADMIN");
    await flushPromises();

    expect(patch).toHaveBeenCalledWith("/usuarios/user-2", { role: "ADMIN" });
  });
});
