<script setup lang="ts">
import type { EapAxisTip } from "~/composables/useEapAxisBadges";

defineProps<{ tip: EapAxisTip | null }>();
</script>

<template>
  <span
    v-if="tip"
    class="eap-axis-tip"
    role="tooltip"
    :style="{ left: `${tip.left}px`, top: `${tip.top}px`, maxWidth: `${tip.maxWidth}px` }"
  >{{ tip.text }}</span>
</template>

<style scoped>
.eap-axis-tip {
  position: fixed;
  z-index: 70;
  padding: 5px 10px;
  border-radius: 9px;
  background: #2b3e58;
  color: #fff;
  font-size: 11.5px;
  font-weight: 700;
  line-height: 1.45;
  white-space: pre-wrap;
  pointer-events: none;
  box-shadow: 0 6px 18px rgb(20 37 58 / 18%);
  transform: translateY(-50%);
}
.eap-axis-tip::before {
  position: absolute;
  top: 50%;
  right: 100%;
  border: 5px solid transparent;
  border-right-color: #2b3e58;
  content: "";
  transform: translateY(-50%);
}
</style>
