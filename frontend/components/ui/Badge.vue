<script setup lang="ts">
import { computed } from "vue";
import { ElTag } from "element-plus";

/**
 * Badge construído sobre o `ElTag` do Element Plus (pill, `effect="light"`).
 * Os tokens de cor vêm do tema EP (`assets/css/element-plus.css`); as variantes
 * neutras do Hub (`secondary`, `outline`) recebem classes próprias porque o
 * `--el-color-info` do Hub é azul.
 */
const props = withDefaults(
  defineProps<{
    variant?: "default" | "secondary" | "success" | "destructive" | "warning" | "outline";
    class?: string;
  }>(),
  { variant: "default", class: undefined },
);

const TYPE_BY_VARIANT = {
  default: "primary",
  secondary: "info",
  success: "success",
  destructive: "danger",
  warning: "warning",
  outline: "info",
} as const;

const type = computed(() => TYPE_BY_VARIANT[props.variant ?? "default"]);
const effect = computed(() => (props.variant === "outline" ? "plain" : "light"));
const badgeClass = computed(() => {
  if (props.variant === "secondary") return "hub-badge--secondary";
  if (props.variant === "outline") return "hub-badge--outline";
  return undefined;
});
</script>

<template>
  <ElTag
    round
    size="small"
    :type="type"
    :effect="effect"
    :class="[badgeClass, props.class]"
  >
    <slot />
  </ElTag>
</template>

<style scoped>
.hub-badge--secondary {
  background: hsl(var(--secondary));
  border-color: transparent;
  color: hsl(var(--secondary-foreground));
}

.hub-badge--outline {
  background: transparent;
  border-color: hsl(var(--border));
  color: hsl(var(--foreground));
}
</style>
