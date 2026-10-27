<script setup lang="ts">
import { computed } from "vue";
import { ElButton } from "element-plus";

/** Semantic adapter: presentation and interaction belong to Element Plus. */
const props = withDefaults(defineProps<{
  variant?: "default" | "outline" | "secondary" | "ghost" | "destructive" | "success" | "link";
  size?: "default" | "sm" | "icon" | "icon-sm";
  type?: "button" | "submit" | "reset";
  loading?: boolean;
  disabled?: boolean;
}>(), { variant: "default", size: "default", type: "button", loading: false, disabled: false });

const appearance = computed(() => {
  switch (props.variant) {
    case "outline": return { plain: true };
    case "secondary": return { type: "primary" as const, plain: true };
    case "ghost": return { text: true };
    case "destructive": return { type: "danger" as const, plain: true };
    case "success": return { type: "success" as const };
    case "link": return { type: "primary" as const, link: true };
    default: return { type: "primary" as const };
  }
});
</script>

<template>
  <ElButton
    v-bind="appearance"
    data-slot="button"
    :native-type="props.type"
    :size="props.size === 'sm' || props.size === 'icon-sm' ? 'small' : 'default'"
    :circle="props.size === 'icon' || props.size === 'icon-sm'"
    :disabled="props.disabled || props.loading"
    :loading="props.loading"
    :aria-busy="props.loading || undefined"
  >
    <slot />
  </ElButton>
</template>
