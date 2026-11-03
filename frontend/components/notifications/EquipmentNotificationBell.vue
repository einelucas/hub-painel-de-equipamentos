<script setup lang="ts">
import { mdiBellOutline } from "@mdi/js";
import { mergeProps, ref, watch } from "vue";
import { VBadge, VBtn, VMenu, VTooltip } from "vuetify/components";
import type {
  EquipmentUserNotification,
  PendingReopenApproval,
} from "~/types/notifications";
import EquipmentNotificationPopover from "~/components/notifications/EquipmentNotificationPopover.vue";

const router = useRouter();
const menuOpen = ref(false);
const center = useEquipmentNotifications();

watch(menuOpen, (open) => {
  if (open) void center.refresh(true);
});

async function openNotification(item: EquipmentUserNotification): Promise<void> {
  if (!item.readAt) {
    try {
      await center.markRead(item);
    } catch {
      // O erro fica visível no popover; a navegação continua disponível.
    }
  }
  if (item.targetUrl) await router.push(item.targetUrl);
  menuOpen.value = false;
}

async function openApproval(item: PendingReopenApproval): Promise<void> {
  await router.push(item.targetUrl);
  menuOpen.value = false;
}
</script>

<template>
  <div class="equipment-notifications" data-testid="equipment-notification-bell">
    <VMenu
      v-model="menuOpen"
      location="bottom end"
      :offset="8"
      :close-on-content-click="false"
      content-class="equipment-notification-menu"
    >
      <template #activator="{ props: menuProps }">
        <VTooltip text="Notificações do Painel de Equipamentos" location="bottom">
          <template #activator="{ props: tooltipProps }">
            <VBadge
              :model-value="center.unreadCount.value > 0"
              :content="center.unreadCount.value"
              :max="99"
              color="error"
              location="top end"
              offset-x="2"
              offset-y="2"
            >
              <VBtn
                class="module-action"
                :icon="mdiBellOutline"
                variant="text"
                aria-label="Abrir notificações do Painel de Equipamentos"
                v-bind="mergeProps(menuProps, tooltipProps)"
              />
            </VBadge>
          </template>
        </VTooltip>
      </template>

      <EquipmentNotificationPopover
        :tab="center.tab.value"
        :notifications="center.notifications.value"
        :approvals="center.approvals.value"
        :unread-count="center.unreadCount.value"
        :pending-count="center.pendingCount.value"
        :can-approve="center.canApprove.value"
        :loading="center.loading.value"
        :busy="center.busy.value"
        :error="center.error.value"
        :feedback="center.feedback.value"
        @select-tab="center.selectTab"
        @read="center.markRead"
        @read-all="center.markAllRead"
        @open-notification="openNotification"
        @open-approval="openApproval"
        @clear-feedback="center.feedback.value = ''"
      />
    </VMenu>
  </div>
</template>

<style scoped>
.equipment-notifications {
  display: flex;
  margin-left: auto;
  align-items: center;
}
</style>
