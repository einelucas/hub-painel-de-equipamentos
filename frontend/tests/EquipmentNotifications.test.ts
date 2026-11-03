import { mount } from "@vue/test-utils";
import { computed, nextTick, ref } from "vue";
import { VBadge, VBtn, VMenu, VTabs } from "vuetify/components";
import { beforeEach, describe, expect, it, vi } from "vitest";
import EquipmentNotificationBell from "~/components/notifications/EquipmentNotificationBell.vue";
import EquipmentNotificationPopover from "~/components/notifications/EquipmentNotificationPopover.vue";
import TabsNav from "~/components/TabsNav.vue";
import type {
  EquipmentUserNotification,
  PendingReopenApproval,
} from "~/types/notifications";

const notification: EquipmentUserNotification = {
  id: "notification-1",
  moduleKey: "EQUIPMENT_PANEL",
  eventType: "REOPEN_REQUESTED",
  equipmentId: "equipment-1",
  equipmentName: "Caldeira",
  projectContextName: "LEM C2",
  unitName: "Luís Eduardo Magalhães",
  reopenRequestId: "reopen-1",
  actor: { id: "analyst-1", name: "Analista", email: "analyst@example.com" },
  title: "Regressão aguardando aprovação",
  message: "Fase atual: 6 — SC ou OCI\nFase solicitada: 3 — Abertura do chamado",
  targetUrl: "/equipamentos/equipment-1?reopen=reopen-1#reabertura",
  createdAt: "2026-11-03T10:00:00Z",
  readAt: null,
};

const approval: PendingReopenApproval = {
  id: "reopen-1",
  equipmentId: "equipment-1",
  equipmentName: "Caldeira",
  projectContextName: "LEM C2",
  unitName: "Luís Eduardo Magalhães",
  sourceStage: 6,
  sourceStageLabel: "SC ou OCI",
  targetStage: 3,
  targetStageLabel: "Abertura do chamado",
  justification: "Revisar processo",
  requestedBy: { id: "analyst-1", name: "Analista", email: "analyst@example.com" },
  requestedAt: "2026-11-03T10:00:00Z",
  targetUrl: "/equipamentos/equipment-1?reopen=reopen-1#reabertura",
};

function popoverProps(overrides: Record<string, unknown> = {}) {
  return {
    tab: "all" as const,
    notifications: [notification],
    approvals: [],
    unreadCount: 1,
    pendingCount: 0,
    canApprove: false,
    loading: false,
    busy: false,
    error: "",
    feedback: "",
    ...overrides,
  };
}

describe("Central de notificações do Painel", () => {
  beforeEach(() => {
    vi.stubGlobal("useRoute", () => ({ path: "/equipamentos" }));
    vi.stubGlobal("useAuthStore", () => ({ can: () => true }));
  });

  it("mantém o sino como último elemento funcional dentro da navbar", () => {
    const wrapper = mount(TabsNav, {
      global: {
        stubs: {
          NuxtLink: { props: ["to"], template: "<a :href='to'><slot /></a>" },
          ImportEquipmentButton: { template: "<button>Importar</button>" },
          NewProjectButton: { template: "<button>Novo projeto</button>" },
          EmailSettingsButton: { template: "<button>E-mails</button>" },
          EquipmentNotificationBell: {
            template: "<div data-testid='equipment-notification-bell' />",
          },
        },
      },
    });

    const nav = wrapper.get("#tabsNav");
    expect(nav.attributes("aria-label")).toContain("Painel de Equipamentos");
    expect(nav.element.lastElementChild?.getAttribute("data-testid")).toBe(
      "equipment-notification-bell",
    );
  });

  it("usa VMenu, VBadge e VBtn nativos no sino e abre o menu pelo ativador", async () => {
    const center = {
      tab: ref("all"),
      notifications: ref([notification]),
      approvals: ref([]),
      unreadCount: ref(1),
      pendingCount: ref(0),
      loading: ref(false),
      busy: ref(false),
      error: ref(""),
      feedback: ref(""),
      canApprove: computed(() => false),
      refresh: vi.fn().mockResolvedValue(undefined),
      selectTab: vi.fn(),
      markRead: vi.fn(),
      markAllRead: vi.fn(),
    };
    vi.stubGlobal("useEquipmentNotifications", () => center);
    vi.stubGlobal("useRouter", () => ({ push: vi.fn() }));

    const wrapper = mount(EquipmentNotificationBell, {
      global: {
        stubs: {
          EquipmentNotificationPopover: { template: "<div>Notificações</div>" },
        },
      },
    });
    expect(wrapper.findComponent(VMenu).exists()).toBe(true);
    expect(wrapper.findComponent(VBadge).props("content")).toBe(1);
    const button = wrapper.findComponent(VBtn);
    expect(button.attributes("aria-label")).toContain("notificações");
    await button.trigger("click");
    await nextTick();
    expect(wrapper.findComponent(VMenu).props("modelValue")).toBe(true);
  });

  it("filtra aprovações pela permissão e apresenta loading nativo", () => {
    const analyst = mount(EquipmentNotificationPopover, {
      props: popoverProps({ loading: true }),
    });
    expect(analyst.findComponent(VTabs).exists()).toBe(true);
    expect(analyst.text()).not.toContain("Aprovações");
    expect(analyst.find(".v-skeleton-loader").exists()).toBe(true);

    const admin = mount(EquipmentNotificationPopover, {
      props: popoverProps({
        tab: "approvals",
        notifications: [],
        approvals: [approval],
        canApprove: true,
        pendingCount: 1,
      }),
    });
    expect(admin.text()).toContain("Aprovações");
    expect(admin.text()).toContain("Caldeira");
    expect(admin.text()).toContain("Pendente");
  });

  it("exibe notificação não lida e emite a navegação sem aprovar automaticamente", async () => {
    const wrapper = mount(EquipmentNotificationPopover, {
      props: popoverProps(),
    });
    expect(wrapper.text()).toContain("Regressão aguardando aprovação");
    expect(wrapper.text()).toContain("LEM C2");
    await wrapper.get(".notification-item").trigger("click");
    expect(wrapper.emitted("openNotification")?.[0]).toEqual([notification]);
    expect(wrapper.emitted("openApproval")).toBeUndefined();
  });
});
