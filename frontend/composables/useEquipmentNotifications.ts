import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import type {
  EquipmentNotificationList,
  EquipmentUserNotification,
  PendingReopenApproval,
  PendingReopenApprovalList,
} from "~/types/notifications";

export type EquipmentNotificationTab = "all" | "unread" | "approvals";

export const EQUIPMENT_NOTIFICATIONS_REFRESH_EVENT =
  "equipment-notifications:refresh";

export function signalEquipmentNotificationsRefresh(): void {
  if (import.meta.client) {
    window.dispatchEvent(new Event(EQUIPMENT_NOTIFICATIONS_REFRESH_EVENT));
  }
}

export function useEquipmentNotifications() {
  const api = useApi();
  const auth = useAuthStore();
  const tab = ref<EquipmentNotificationTab>("all");
  const notifications = ref<EquipmentUserNotification[]>([]);
  const approvals = ref<PendingReopenApproval[]>([]);
  const unreadCount = ref(0);
  const pendingCount = ref(0);
  const loading = ref(false);
  const busy = ref(false);
  const error = ref("");
  const feedback = ref("");
  let countsInFlight: Promise<void> | null = null;
  let listRequestId = 0;
  let pollTimer: ReturnType<typeof setInterval> | undefined;

  const canApprove = computed(() => auth.can("workflow:reopen_approve"));

  async function loadCounts(): Promise<void> {
    if (!auth.authenticated) return;
    const requests: [Promise<{ count: number }>, Promise<PendingReopenApprovalList> | null] = [
      api.get<{ count: number }>("/notifications/unread-count"),
      canApprove.value
        ? api.get<PendingReopenApprovalList>("/notifications/pending-approvals", {
            page: 1,
            pageSize: 1,
          })
        : null,
    ];
    const [unread, pending] = await Promise.all([
      requests[0],
      requests[1] ?? Promise.resolve(null),
    ]);
    unreadCount.value = unread.count;
    pendingCount.value = pending?.pagination.total ?? 0;
  }

  function loadCountsOnce(): Promise<void> {
    if (!countsInFlight) {
      countsInFlight = loadCounts().finally(() => {
        countsInFlight = null;
      });
    }
    return countsInFlight;
  }

  async function loadSelectedTab(): Promise<void> {
    if (tab.value === "approvals") {
      if (!canApprove.value) {
        tab.value = "all";
        return loadSelectedTab();
      }
      const result = await api.get<PendingReopenApprovalList>(
        "/notifications/pending-approvals",
        { page: 1, pageSize: 40 },
      );
      approvals.value = result.items;
      pendingCount.value = result.pagination.total;
      return;
    }
    const result = await api.get<EquipmentNotificationList>("/notifications/inbox", {
      page: 1,
      pageSize: 40,
      unreadOnly: tab.value === "unread",
    });
    notifications.value = result.items;
  }

  async function refresh(includeList = true): Promise<void> {
    if (!auth.authenticated) return Promise.resolve();
    const requestId = includeList ? ++listRequestId : listRequestId;
    if (includeList) loading.value = true;
    error.value = "";
    try {
      await Promise.all([
        loadCountsOnce(),
        includeList ? loadSelectedTab() : Promise.resolve(),
      ]);
    } catch (caught) {
      error.value =
        caught instanceof Error
          ? caught.message
          : "Não foi possível atualizar as notificações.";
    } finally {
      if (includeList && requestId === listRequestId) loading.value = false;
    }
  }

  async function selectTab(value: EquipmentNotificationTab): Promise<void> {
    if (value === "approvals" && !canApprove.value) return;
    tab.value = value;
    await refresh(true);
  }

  async function markRead(item: EquipmentUserNotification): Promise<void> {
    if (item.readAt || busy.value) return;
    busy.value = true;
    error.value = "";
    try {
      const updated = await api.patch<EquipmentUserNotification>(
        `/notifications/${item.id}/read`,
      );
      notifications.value = notifications.value
        .map((entry) => (entry.id === item.id ? updated : entry))
        .filter((entry) => tab.value !== "unread" || !entry.readAt);
      unreadCount.value = Math.max(0, unreadCount.value - 1);
    } catch (caught) {
      error.value =
        caught instanceof Error ? caught.message : "Não foi possível marcar como lida.";
      throw caught;
    } finally {
      busy.value = false;
    }
  }

  async function markAllRead(): Promise<void> {
    if (!unreadCount.value || busy.value) return;
    busy.value = true;
    error.value = "";
    try {
      const result = await api.post<{ updated: number }>("/notifications/read-all");
      notifications.value =
        tab.value === "unread"
          ? []
          : notifications.value.map((item) => ({
              ...item,
              readAt: item.readAt ?? new Date().toISOString(),
            }));
      unreadCount.value = 0;
      feedback.value = `${result.updated} notificação(ões) marcada(s) como lida(s).`;
    } catch (caught) {
      error.value =
        caught instanceof Error
          ? caught.message
          : "Não foi possível marcar todas como lidas.";
    } finally {
      busy.value = false;
    }
  }

  function onVisible(): void {
    if (!document.hidden) void refresh(false);
  }

  function startPolling(): void {
    stopPolling();
    if (!auth.authenticated) return;
    void refresh(false);
    pollTimer = setInterval(() => {
      if (!document.hidden) void refresh(false);
    }, 45_000);
  }

  function stopPolling(): void {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = undefined;
  }

  function onDomainChange(): void {
    void refresh(true);
  }

  watch(
    () => auth.authenticated,
    (authenticated) => {
      if (authenticated) startPolling();
      else {
        stopPolling();
        notifications.value = [];
        approvals.value = [];
        unreadCount.value = 0;
        pendingCount.value = 0;
      }
    },
  );

  onMounted(() => {
    document.addEventListener("visibilitychange", onVisible);
    window.addEventListener(EQUIPMENT_NOTIFICATIONS_REFRESH_EVENT, onDomainChange);
    startPolling();
  });
  onBeforeUnmount(() => {
    stopPolling();
    document.removeEventListener("visibilitychange", onVisible);
    window.removeEventListener(EQUIPMENT_NOTIFICATIONS_REFRESH_EVENT, onDomainChange);
  });

  return {
    tab,
    notifications,
    approvals,
    unreadCount,
    pendingCount,
    loading,
    busy,
    error,
    feedback,
    canApprove,
    refresh,
    selectTab,
    markRead,
    markAllRead,
  };
}
