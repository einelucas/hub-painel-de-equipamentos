<script setup lang="ts">
import { computed } from "vue";
import type { Component } from "vue";
import { CalendarDays, ChartNoAxesCombined, MapPinned } from "lucide-vue-next";

interface NavItem {
  value: string;
  label: string;
  icon?: Component;
}

const defaultItems: NavItem[] = [
  { value: "eap", label: "Áreas e projetos", icon: MapPinned },
  { value: "schedule", label: "Entregas", icon: CalendarDays },
  { value: "finance", label: "Financeiro e evolução", icon: ChartNoAxesCombined },
];

const props = defineProps<{ modelValue: string; items?: NavItem[]; distributed?: boolean }>();
const emit = defineEmits<{ "update:modelValue": [value: string] }>();

const resolvedItems = computed(() => props.items ?? defaultItems);

function select(value: string): void {
  emit("update:modelValue", value);
}
</script>

<template>
  <nav class="analysis-nav" :class="{ 'analysis-nav--distributed': props.distributed }" role="tablist" aria-label="Análises complementares">
    <button
      v-for="item in resolvedItems"
      :key="item.value"
      type="button"
      role="tab"
      :aria-selected="modelValue === item.value"
      :class="['analysis-nav__item', { 'is-active': modelValue === item.value }]"
      @click="select(item.value)"
    >
      <component :is="item.icon" class="analysis-nav__icon" :size="16" aria-hidden="true" />
      <span>{{ item.label }}</span>
    </button>
  </nav>
</template>

<style scoped>
.analysis-nav {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-start;
  align-items: center;
  gap: 4px;
  padding: 6px;
  border: 1px solid #e9eef4;
  border-radius: 12px;
  background: #f4f7fb;
  width: 100%;
  max-width: 100%;
  margin: 0;
}

.analysis-nav__item {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 9px 15px;
  border: 1px solid transparent;
  border-radius: 9px;
  background: transparent;
  color: #607085;
  font-size: 12.5px;
  font-weight: 700;
  line-height: 1;
  cursor: pointer;
  transition: background-color 0.16s ease, color 0.16s ease, border-color 0.16s ease, box-shadow 0.16s ease;
}

.analysis-nav__icon {
  flex: none;
  opacity: 0.78;
}

.analysis-nav__item:hover {
  background: #e8edf4;
  color: #304f7e;
}

.analysis-nav__item.is-active {
  background: #ffffff;
  color: #213758;
  border-color: #e9eef4;
  box-shadow: 0 1px 3px rgba(33, 55, 88, 0.08);
}

.analysis-nav__item.is-active .analysis-nav__icon {
  opacity: 1;
  color: #304f7e;
}

.analysis-nav__item:focus-visible {
  outline: 2px solid #304f7e;
  outline-offset: 2px;
}

.analysis-nav--distributed {
  justify-content: stretch;
}

.analysis-nav--distributed .analysis-nav__item {
  flex: 1 1 0;
  min-width: 0;
  justify-content: center;
}
</style>