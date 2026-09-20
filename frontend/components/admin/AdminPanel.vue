<script setup lang="ts">
/**
 * Casca do painel administrativo contextual.
 *
 * Mora dentro da aba onde o dado é usado — o usuário não sai da tela. Só cuida
 * de layout, abas e estados; cada seção traz seu próprio conteúdo por slot.
 */
const props = defineProps<{
  open: boolean;
  title: string;
  description: string;
  sections: { key: string; label: string }[];
}>();
const emit = defineEmits<{ close: [] }>();

const active = defineModel<string>("section", { required: true });

watch(
  () => props.open,
  (isOpen) => {
    if (isOpen && !props.sections.some((item) => item.key === active.value)) {
      active.value = props.sections[0]?.key ?? "";
    }
  },
);
</script>

<template>
  <AppModal :open="props.open" :title="props.title" @close="emit('close')">
    <div class="admin-panel" data-testid="admin-panel">
      <p class="admin-description">{{ props.description }}</p>

      <div v-if="props.sections.length > 1" class="admin-tabs" role="tablist">
        <button
          v-for="section in props.sections"
          :key="section.key"
          type="button"
          role="tab"
          :class="{ active: active === section.key }"
          :aria-selected="active === section.key"
          :data-testid="`admin-tab-${section.key}`"
          @click="active = section.key"
        >
          {{ section.label }}
        </button>
      </div>

      <div class="admin-body">
        <slot :section="active" />
      </div>
    </div>
  </AppModal>
</template>

<style scoped>
/* Sem min-width: a largura é a do .modal-card do Hub (680px), que é baseline. */
.admin-panel { display: grid; gap: 14px; }
.admin-description { margin: 0; color: #65748a; font-size: 12.5px; }
.admin-tabs { display: flex; flex-wrap: wrap; gap: 4px; border-bottom: 1px solid #e4e9f0; }
.admin-tabs button { border: 0; border-bottom: 2px solid transparent; padding: 8px 12px; background: transparent; color: #7a879a; font-size: 12px; font-weight: 750; }
.admin-tabs button.active { border-bottom-color: #304f7e; color: #2b3e58; }
.admin-tabs button:focus-visible { outline: 2px solid #304f7e; outline-offset: 2px; }
.admin-body { max-height: min(60vh, 520px); overflow-y: auto; }
</style>
