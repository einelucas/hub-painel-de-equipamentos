<script setup lang="ts">
import type { StyleValue } from "vue";
import { cn } from "~/utils/cn";

const props = withDefaults(defineProps<{
  class?: string;
  style?: StyleValue;
  loading?: boolean;
}>(), {
  class: undefined,
  style: undefined,
  loading: false,
});

</script>

<template>
  <div
    class="w-full overflow-x-auto rounded-lg border border-border"
    :aria-busy="props.loading"
  >
    <table data-slot="table" :class="cn('w-full caption-bottom text-sm', props.class)" :style="props.style">
      <slot />
    </table>
  </div>
</template>
