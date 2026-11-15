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
import { Building2, Clock3, UserRound } from "lucide-vue-next";
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
      <span v-if="item.projectContextName || item.unitName" class="notification-item__context">
        <Building2 :size="14" aria-hidden="true" />
        <span>
          {{ item.projectContextName ?? "Obra não informada" }} ·
          {{ item.unitName ?? "Unidade não informada" }}
        </span>
      </span>
      <span class="notification-item__message">{{ item.message }}</span>
      <span class="notification-item__meta">
        <span v-if="item.actor"><UserRound :size="13" aria-hidden="true" />{{ item.actor.name }}</span>
        <span><Clock3 :size="13" aria-hidden="true" />{{ formatDateTime(item.createdAt) }}</span>
      </span>
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
.notification-item { align-items: flex-start; min-height: 0; padding: 13px; border: 1px solid #e5eaf1; border-left: 3px solid transparent; border-radius: 12px; background: #fff; transition: border-color .16s ease, box-shadow .16s ease, transform .16s ease; }
.notification-item:hover { border-color: #cfd9e6; box-shadow: 0 6px 18px rgb(33 55 88 / 8%); transform: translateY(-1px); }
.notification-item--unread { border-left-color: #304f7e; background: #f7faff; }
.notification-item :deep(.v-list-item__prepend), .notification-item :deep(.v-list-item__append) { padding-top: 1px; }
.notification-item :deep(.v-list-item__content) { min-width: 0; }
.notification-item__icon {
  display: grid;
  width: 34px;
  height: 34px;
  place-items: center;
  border-radius: 10px;
  background: #eaf0f8;
  color: #304f7e;
}
.notification-item__title { color: #536a86; font-size: 11px; font-weight: 750; white-space: normal; }
.notification-item__subtitle { display: grid; overflow: visible; gap: 7px; padding-top: 5px; color: #6c7b90; opacity: 1; -webkit-line-clamp: unset; }
.notification-item__subtitle strong { color: #253a59; font-size: 13px; line-height: 1.35; }
.notification-item__context, .notification-item__meta, .notification-item__meta span { display: flex; align-items: center; }
.notification-item__context { gap: 6px; color: #708096; font-size: 11px; }
.notification-item__context > span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.notification-item__message {
  display: block;
  padding: 8px 10px;
  border-radius: 9px;
  background: #f3f6fa;
  color: #4c617b;
  font-size: 11px;
  line-height: 1.5;
  white-space: pre-line;
}
.notification-item__meta { flex-wrap: wrap; gap: 7px 14px; color: #8793a4; font-size: 10.5px; }
.notification-item__meta span { gap: 5px; }
.notification-item__actions { display: flex; align-items: center; gap: 2px; }
</style>
