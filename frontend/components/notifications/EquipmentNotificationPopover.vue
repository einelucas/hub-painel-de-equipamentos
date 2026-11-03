<script setup lang="ts">
import { mdiCheckAll } from "@mdi/js";
import {
  VAlert,
  VBtn,
  VCard,
  VCardTitle,
  VChip,
  VDivider,
  VList,
  VListItem,
  VListItemSubtitle,
  VListItemTitle,
  VSkeletonLoader,
  VSnackbar,
  VTab,
  VTabs,
} from "vuetify/components";
import type {
  EquipmentUserNotification,
  PendingReopenApproval,
} from "~/types/notifications";
import type { EquipmentNotificationTab } from "~/composables/useEquipmentNotifications";
import EquipmentNotificationItem from "~/components/notifications/EquipmentNotificationItem.vue";
import { formatDateTime } from "~/utils/format";

defineProps<{
  tab: EquipmentNotificationTab;
  notifications: EquipmentUserNotification[];
  approvals: PendingReopenApproval[];
  unreadCount: number;
  pendingCount: number;
  canApprove: boolean;
  loading: boolean;
  busy: boolean;
  error: string;
  feedback: string;
}>();
const emit = defineEmits<{
  selectTab: [tab: EquipmentNotificationTab];
  read: [item: EquipmentUserNotification];
  readAll: [];
  openNotification: [item: EquipmentUserNotification];
  openApproval: [item: PendingReopenApproval];
  clearFeedback: [];
}>();

function selectTab(value: unknown): void {
  if (value === "all" || value === "unread" || value === "approvals") {
    emit("selectTab", value);
  }
}
</script>

<template>
  <VCard class="notification-popover" width="440" max-width="calc(100vw - 24px)" rounded="lg" elevation="8">
    <VCardTitle class="notification-popover__header">
      <div>
        <strong>Notificações</strong>
        <span>{{ unreadCount }} não lida(s)</span>
      </div>
      <VBtn
        v-if="unreadCount"
        size="small"
        variant="text"
        :prepend-icon="mdiCheckAll"
        :loading="busy"
        @click="emit('readAll')"
      >
        Marcar todas
      </VBtn>
    </VCardTitle>

    <VDivider />
    <VTabs
      :model-value="tab"
      color="primary"
      density="compact"
      grow
      @update:model-value="selectTab"
    >
      <VTab value="all">Todas</VTab>
      <VTab value="unread">
        Não lidas
        <VChip v-if="unreadCount" class="ml-1" size="x-small" color="primary" variant="tonal">
          {{ unreadCount }}
        </VChip>
      </VTab>
      <VTab v-if="canApprove" value="approvals">
        Aprovações
        <VChip v-if="pendingCount" class="ml-1" size="x-small" color="warning" variant="tonal">
          {{ pendingCount }}
        </VChip>
      </VTab>
    </VTabs>
    <VDivider />

    <VAlert v-if="error" class="ma-3 mb-0" type="error" variant="tonal" density="compact">
      {{ error }}
    </VAlert>

    <VSkeletonLoader
      v-if="loading"
      class="notification-popover__loading"
      type="list-item-avatar-two-line@4"
      aria-label="Carregando notificações"
    />

    <VList v-else-if="tab !== 'approvals' && notifications.length" class="notification-popover__list" lines="three">
      <template v-for="(item, index) in notifications" :key="item.id">
        <EquipmentNotificationItem
          :item="item"
          :busy="busy"
          @read="emit('read', $event)"
          @open="emit('openNotification', $event)"
        />
        <VDivider v-if="index < notifications.length - 1" />
      </template>
    </VList>

    <VList v-else-if="tab === 'approvals' && approvals.length" class="notification-popover__list" lines="three">
      <template v-for="(item, index) in approvals" :key="item.id">
        <VListItem class="approval-item" @click="emit('openApproval', item)">
          <VListItemTitle>{{ item.equipmentName }}</VListItemTitle>
          <VListItemSubtitle>
            <span>{{ item.projectContextName }} · {{ item.unitName }}</span>
            <span>{{ item.sourceStage }} — {{ item.sourceStageLabel }} → {{ item.targetStage }} — {{ item.targetStageLabel }}</span>
            <span>{{ item.requestedBy?.name ?? "Usuário removido" }} · {{ formatDateTime(item.requestedAt) }}</span>
          </VListItemSubtitle>
          <template #append>
            <VChip color="warning" size="x-small" variant="tonal">Pendente</VChip>
          </template>
        </VListItem>
        <VDivider v-if="index < approvals.length - 1" />
      </template>
    </VList>

    <VAlert v-else class="ma-4" type="info" variant="tonal" density="compact">
      {{ tab === "approvals" ? "Nenhuma regressão aguardando decisão." : "Nenhuma notificação nesta categoria." }}
    </VAlert>

    <VSnackbar
      :model-value="Boolean(feedback)"
      color="success"
      location="bottom end"
      :timeout="4000"
      @update:model-value="!$event && emit('clearFeedback')"
    >
      {{ feedback }}
    </VSnackbar>
  </VCard>
</template>

<style scoped>
.notification-popover { overflow: hidden; }
.notification-popover__header {
  display: flex;
  min-height: 62px;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 16px;
}
.notification-popover__header > div { display: grid; gap: 2px; }
.notification-popover__header strong { color: #213758; font-size: 16px; }
.notification-popover__header span { color: #718096; font-size: 11px; font-weight: 500; }
.notification-popover__loading { min-height: 340px; }
.notification-popover__list { max-height: min(520px, calc(100vh - 210px)); overflow-y: auto; padding: 0; }
.approval-item { min-height: 94px; }
.approval-item :deep(.v-list-item-subtitle) { display: grid; gap: 3px; padding-top: 4px; }
@media (max-width: 520px) {
  .notification-popover__header { align-items: flex-start; flex-direction: column; }
  .notification-popover__list { max-height: calc(100vh - 250px); }
}
</style>
