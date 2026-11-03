<script setup lang="ts">
import {
  mdiBellOutline,
  mdiCheck,
  mdiCheckCircleOutline,
  mdiClockAlertOutline,
  mdiCloseCircleOutline,
  mdiRestore,
} from "@mdi/js";
import { computed } from "vue";
import {
  VBtn,
  VChip,
  VIcon,
  VListItem,
  VListItemSubtitle,
  VListItemTitle,
} from "vuetify/components";
import type { EquipmentUserNotification } from "~/types/notifications";
import { formatDateTime } from "~/utils/format";

const props = defineProps<{ item: EquipmentUserNotification; busy: boolean }>();
const emit = defineEmits<{
  open: [item: EquipmentUserNotification];
  read: [item: EquipmentUserNotification];
}>();

const icon = computed(() => {
  if (props.item.eventType === "REOPEN_REQUESTED") return mdiRestore;
  if (props.item.eventType === "REOPEN_APPROVED") return mdiCheckCircleOutline;
  if (props.item.eventType === "REOPEN_REJECTED") return mdiCloseCircleOutline;
  if (props.item.eventType.includes("REMINDER") || props.item.eventType.includes("OVERDUE")) {
    return mdiClockAlertOutline;
  }
  return mdiBellOutline;
});
</script>

<template>
  <VListItem
    class="notification-item"
    :class="{ 'notification-item--unread': !item.readAt }"
    :aria-label="`${item.title}. ${item.equipmentName ?? ''}`"
    @click="emit('open', item)"
  >
    <template #prepend>
      <span class="notification-item__icon" aria-hidden="true">
        <VIcon :icon="icon" size="19" />
      </span>
    </template>

    <VListItemTitle class="notification-item__title">
      {{ item.title }}
    </VListItemTitle>
    <VListItemSubtitle class="notification-item__subtitle">
      <strong v-if="item.equipmentName">{{ item.equipmentName }}</strong>
      <span v-if="item.projectContextName || item.unitName">
        {{ item.projectContextName ?? "Obra não informada" }} ·
        {{ item.unitName ?? "Unidade não informada" }}
      </span>
      <span class="notification-item__message">{{ item.message }}</span>
      <span>{{ formatDateTime(item.createdAt) }}</span>
    </VListItemSubtitle>

    <template #append>
      <div class="notification-item__actions">
        <VChip
          v-if="!item.readAt"
          color="primary"
          size="x-small"
          variant="tonal"
        >
          Nova
        </VChip>
        <VBtn
          v-if="!item.readAt"
          :icon="mdiCheck"
          size="x-small"
          variant="text"
          :disabled="busy"
          aria-label="Marcar notificação como lida"
          @click.stop="emit('read', item)"
        />
      </div>
    </template>
  </VListItem>
</template>

<style scoped>
.notification-item { min-height: 112px; border-left: 3px solid transparent; }
.notification-item--unread { border-left-color: #304f7e; background: #f6f9fd; }
.notification-item__icon {
  display: grid;
  width: 34px;
  height: 34px;
  place-items: center;
  border-radius: 10px;
  background: #eaf0f8;
  color: #304f7e;
}
.notification-item__title { color: #253a59; font-size: 13px; font-weight: 750; }
.notification-item__subtitle { display: grid; gap: 3px; padding-top: 4px; color: #6c7b90; }
.notification-item__subtitle strong { color: #405672; }
.notification-item__message {
  display: -webkit-box;
  overflow: hidden;
  white-space: pre-line;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}
.notification-item__actions { display: flex; align-items: center; gap: 2px; }
</style>
