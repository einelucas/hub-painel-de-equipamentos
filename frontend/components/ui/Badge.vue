<script setup lang="ts">
import { computed } from "vue";
import { VChip } from "vuetify/components";

/**
 * Rótulo informativo do Hub sobre o `VChip`. Não recebe comportamento de link
 * ou seleção; as variantes públicas continuam mapeadas aos tokens semânticos.
 */
const props = withDefaults(
  defineProps<{
    variant?: "default" | "secondary" | "success" | "destructive" | "warning" | "outline";
    class?: string;
  }>(),
  { variant: "default", class: undefined },
);

const COLOR_BY_VARIANT = {
  default: "primary",
  secondary: "secondary",
  success: "success",
  destructive: "error",
  warning: "warning",
  outline: "secondary",
} as const;

const color = computed(() => COLOR_BY_VARIANT[props.variant ?? "default"]);
const chipVariant = computed(() => {
  if (props.variant === "outline") return "outlined" as const;
  if (props.variant === "secondary") return "flat" as const;
  return "tonal" as const;
});
</script>

<template>
  <VChip
    size="small"
    density="compact"
    rounded="pill"
    :color="color"
    :variant="chipVariant"
    :class="props.class"
  >
    <template v-if="$slots.prepend" #prepend><slot name="prepend" /></template>
    <slot />
    <template v-if="$slots.append" #append><slot name="append" /></template>
  </VChip>
</template>
