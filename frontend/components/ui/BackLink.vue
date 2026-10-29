<script setup lang="ts">
import { mdiArrowLeft } from "@mdi/js";
import { VBtn } from "vuetify/components";
import { ArrowLeft } from "lucide-vue-next";

withDefaults(
  defineProps<{
    to?: string;
    compact?: boolean;
  }>(),
  { to: undefined, compact: false },
);

const emit = defineEmits<{ click: [event: MouseEvent] }>();
</script>

<template>
  <NuxtLink
    v-if="to"
    :to="to"
    class="back-link"
    :class="{ 'back-link--compact': compact }"
    @click="emit('click', $event)"
  >
    <span class="back-link__icon" aria-hidden="true">
      <ArrowLeft :size="compact ? 15 : 16" :stroke-width="2.2" />
    </span>
    <span class="back-link__label"><slot>Voltar</slot></span>
  </NuxtLink>

  <VBtn
    v-else
    variant="outlined"
    type="button"
    :size="compact ? 'x-small' : 'small'"
    :prepend-icon="mdiArrowLeft"
    @click="emit('click', $event)"
  >
    <slot>Voltar</slot>
  </VBtn>
</template>

<style scoped>
.back-link {
  --back-link-ink: #304f7e;
  --back-link-border: #dbe4ef;

  display: inline-flex;
  min-height: 38px;
  align-items: center;
  gap: 9px;
  padding: 5px 14px 5px 5px;
  border: 1px solid var(--back-link-border);
  border-radius: 999px;
  background: linear-gradient(180deg, #ffffff 0%, #fbfcfe 100%);
  color: #41546d;
  font-family: inherit;
  font-size: 12.5px;
  font-weight: 700;
  line-height: 1;
  text-decoration: none;
  cursor: pointer;
  box-shadow:
    0 1px 2px rgba(23, 43, 77, 0.04),
    0 5px 12px -9px rgba(23, 43, 77, 0.35);
  transition:
    color 0.18s ease,
    border-color 0.18s ease,
    background 0.18s ease,
    box-shadow 0.18s ease,
    transform 0.18s ease;
}

.back-link:hover {
  border-color: #c4d4e8;
  background: #ffffff;
  color: #213758;
  box-shadow:
    0 2px 4px rgba(23, 43, 77, 0.05),
    0 8px 18px -10px rgba(23, 43, 77, 0.4);
}

.back-link__icon {
  display: grid;
  width: 28px;
  height: 28px;
  flex: 0 0 auto;
  place-items: center;
  border-radius: 999px;
  background: #edf3fb;
  color: var(--back-link-ink);
  box-shadow: inset 0 0 0 1px rgba(48, 79, 126, 0.06);
  transition:
    color 0.18s ease,
    background 0.18s ease,
    transform 0.18s ease;
}

.back-link:hover .back-link__icon {
  background: var(--back-link-ink);
  color: #ffffff;
  transform: translateX(-1px);
}

.back-link:active {
  transform: translateY(1px);
}

.back-link:focus-visible {
  outline: none;
  border-color: #8da9ce;
  box-shadow:
    0 0 0 3px rgba(48, 79, 126, 0.16),
    0 2px 5px rgba(23, 43, 77, 0.08);
}

.back-link__label {
  max-width: 230px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.back-link--compact {
  min-height: 34px;
  gap: 7px;
  padding: 3px 12px 3px 3px;
  font-size: 12px;
}

.back-link--compact .back-link__icon {
  width: 26px;
  height: 26px;
}

@media (prefers-reduced-motion: reduce) {
  .back-link,
  .back-link__icon {
    transition: none;
  }

  .back-link:hover .back-link__icon {
    transform: none;
  }
}
</style>
