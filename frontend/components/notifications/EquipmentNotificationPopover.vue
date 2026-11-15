<script setup lang="ts">
import { mdiCheckAll } from "@mdi/js";
import { computed } from "vue";
import {
  ArrowRight,
  Bell,
  Building2,
  Clock3,
  Mail,
  RotateCcw,
  ShieldCheck,
  UserRound,
} from "lucide-vue-next";
import {
  VAlert,
  VBtn,
  VCard,
  VCardTitle,
  VChip,
  VList,
  VListItem,
  VSkeletonLoader,
  VSnackbar,
} from "vuetify/components";
import type {
  EquipmentUserNotification,
  PendingReopenApproval,
} from "~/types/notifications";
import type { EquipmentNotificationTab } from "~/composables/useEquipmentNotifications";
import EquipmentNotificationItem from "~/components/notifications/EquipmentNotificationItem.vue";
import NavigationMenu from "~/components/ui/NavigationMenu.vue";
import { formatDateTime } from "~/utils/format";

const props = defineProps<{
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

const navigationItems = computed(() => [
  { value: "all", label: "Todas", icon: Bell },
  {
    value: "unread",
    label: "Não lidas",
    icon: Mail,
    badge: props.unreadCount || undefined,
  },
  ...(props.canApprove
    ? [{
        value: "approvals",
        label: "Aprovações",
        icon: ShieldCheck,
        badge: props.pendingCount || undefined,
      }]
    : []),
]);
</script>

<template>
  <VCard class="notification-popover" width="540" max-width="calc(100vw - 24px)" rounded="lg" elevation="8">
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

    <div class="notification-popover__navigation">
      <NavigationMenu
        :model-value="tab"
        :items="navigationItems"
        distributed
        aria-label="Categorias de notificações"
        @update:model-value="selectTab"
      />
    </div>

    <VAlert v-if="error" class="ma-3 mb-0" type="error" variant="tonal" density="compact">
      {{ error }}
    </VAlert>

    <VSkeletonLoader
      v-if="loading"
      class="notification-popover__loading"
      type="list-item-avatar-two-line@4"
      aria-label="Carregando notificações"
    />

    <VList v-else-if="tab !== 'approvals' && notifications.length" class="notification-popover__list">
      <template v-for="item in notifications" :key="item.id">
        <EquipmentNotificationItem
          :item="item"
          :busy="busy"
          @read="emit('read', $event)"
          @open="emit('openNotification', $event)"
        />
      </template>
    </VList>

    <VList v-else-if="tab === 'approvals' && approvals.length" class="notification-popover__list">
      <template v-for="item in approvals" :key="item.id">
        <VListItem class="approval-item" @click="emit('openApproval', item)">
          <template #prepend>
            <span class="approval-item__icon" aria-hidden="true"><RotateCcw :size="18" /></span>
          </template>
          <div class="approval-item__content">
            <div class="approval-item__heading">
              <strong>{{ item.equipmentName }}</strong>
              <VChip color="warning" size="x-small" variant="tonal">Pendente</VChip>
            </div>
            <div class="approval-item__location">
              <Building2 :size="14" aria-hidden="true" />
              <span>{{ item.projectContextName }} · {{ item.unitName }}</span>
            </div>
            <div class="approval-item__transition">
              <span><small>Etapa atual</small>{{ item.sourceStage }} · {{ item.sourceStageLabel }}</span>
              <ArrowRight :size="16" aria-hidden="true" />
              <span><small>Etapa solicitada</small>{{ item.targetStage }} · {{ item.targetStageLabel }}</span>
            </div>
            <div v-if="item.justification" class="approval-item__justification">
              <small>Justificativa</small>
              <span>{{ item.justification }}</span>
            </div>
            <div class="approval-item__meta">
              <span><UserRound :size="13" aria-hidden="true" />{{ item.requestedBy?.name ?? "Usuário removido" }}</span>
              <span><Clock3 :size="13" aria-hidden="true" />{{ formatDateTime(item.requestedAt) }}</span>
            </div>
          </div>
        </VListItem>
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
.notification-popover__navigation { padding: 0 12px 10px; border-bottom: 1px solid #edf1f5; }
.notification-popover__navigation :deep(.analysis-nav__item) { padding: 8px 10px; font-size: 11.5px; }
.notification-popover__loading { min-height: 340px; }
.notification-popover__list { display: grid; gap: 8px; max-height: min(560px, calc(100vh - 210px)); overflow-y: auto; padding: 10px; background: #f8fafc; }
.approval-item { align-items: flex-start; min-height: 0; padding: 13px; border: 1px solid #e5eaf1; border-radius: 12px; background: #fff; transition: border-color .16s ease, box-shadow .16s ease, transform .16s ease; }
.approval-item:hover { border-color: #cfd9e6; box-shadow: 0 6px 18px rgb(33 55 88 / 8%); transform: translateY(-1px); }
.approval-item :deep(.v-list-item__prepend) { align-self: flex-start; margin-inline-end: 12px; padding-top: 1px; }
.approval-item :deep(.v-list-item__content) { min-width: 0; }
.approval-item__icon { display: grid; width: 34px; height: 34px; place-items: center; border-radius: 10px; background: #fff4df; color: #b67616; }
.approval-item__content { display: grid; gap: 8px; min-width: 0; }
.approval-item__heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; }
.approval-item__heading strong { color: #253a59; font-size: 13px; line-height: 1.35; }
.approval-item__location, .approval-item__meta, .approval-item__meta span { display: flex; align-items: center; }
.approval-item__location { gap: 6px; color: #708096; font-size: 11px; }
.approval-item__location span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.approval-item__transition { display: grid; grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr); align-items: center; gap: 8px; padding: 9px 10px; border-radius: 9px; background: #f3f6fa; color: #415672; font-size: 11px; line-height: 1.35; }
.approval-item__transition > span { display: grid; gap: 2px; min-width: 0; }
.approval-item__transition small, .approval-item__justification small { color: #8a97a8; font-size: 9.5px; font-weight: 750; letter-spacing: .03em; text-transform: uppercase; }
.approval-item__justification { display: grid; gap: 3px; padding-left: 9px; border-left: 2px solid #dbe4ef; color: #566a82; font-size: 11px; line-height: 1.45; }
.approval-item__meta { flex-wrap: wrap; gap: 7px 14px; color: #8793a4; font-size: 10.5px; }
.approval-item__meta span { gap: 5px; }
@media (max-width: 520px) {
  .notification-popover__header { align-items: flex-start; flex-direction: column; }
  .notification-popover__list { max-height: calc(100vh - 250px); }
  .approval-item__transition { grid-template-columns: 1fr; }
  .approval-item__transition > svg { transform: rotate(90deg); }
}
</style>
