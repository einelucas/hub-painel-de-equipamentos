<script setup lang="ts">
import { CalendarClock, ChevronRight, Factory, Timer } from "lucide-vue-next";

import type { StartupSummary } from "~/types/equipment";
import { formatDateOnly } from "~/utils/format";

defineProps<{
  startup: StartupSummary;
  label: string;
}>();
</script>

<template>
  <DashboardCard
    title="Próxima startup"
    subtitle="Menor data futura no recorte."
    :icon="CalendarClock"
  >
    <div class="startup-body">
      <!-- Marco principal -->
      <div class="startup-hero">
        <span class="startup-eyebrow"> Próximo marco </span>

        <div class="startup-date-row">
          <strong class="startup-date">
            {{ formatDateOnly(startup.nextAt) }}
          </strong>

          <span class="startup-countdown">
            <Timer :size="14" />

            {{ label }}
          </span>
        </div>

        <span class="startup-caption"> Startup programada </span>
      </div>

      <!-- Equipamento relacionado -->
      <NuxtLink
        v-if="startup.equipmentId"
        class="equipment-card"
        :to="`/equipamentos/${startup.equipmentId}`"
      >
        <span class="equipment-icon">
          <Factory :size="17" />
        </span>

        <span class="equipment-content">
          <span class="equipment-label"> Equipamento </span>

          <strong class="equipment-name">
            {{ startup.equipmentName }}
          </strong>
        </span>

        <ChevronRight :size="17" class="equipment-arrow" />
      </NuxtLink>

      <div v-else class="equipment-card equipment-card--disabled">
        <span class="equipment-icon">
          <Factory :size="17" />
        </span>

        <span class="equipment-content">
          <span class="equipment-label"> Equipamento </span>

          <strong class="equipment-name"> Não informado </strong>
        </span>
      </div>
    </div>
  </DashboardCard>
</template>

<style scoped>
.startup-body {
  display: flex;
  height: 100%;
  flex-direction: column;
  justify-content: space-between;
  gap: 24px;
}

/* =========================================================
   MARCO PRINCIPAL
   ========================================================= */

.startup-hero {
  display: flex;
  flex-direction: column;

  padding-top: 2px;
}

.startup-eyebrow {
  margin-bottom: 10px;

  color: #8995a7;

  font-size: 9.5px;
  font-weight: 750;

  letter-spacing: 0.07em;
  text-transform: uppercase;
}

.startup-date-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.startup-date {
  color: #203b60;

  font-size: 28px;
  font-weight: 760;
  line-height: 1;

  letter-spacing: -0.02em;
}

/* Countdown */

.startup-countdown {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 6px;

  min-height: 30px;
  padding: 5px 9px;

  border: 1px solid #d8e2ef;
  border-radius: 8px;

  background: #f3f7fb;
  color: #45658e;

  font-size: 11px;
  font-weight: 700;
  white-space: nowrap;
}

.startup-caption {
  margin-top: 8px;

  color: #7f8ca0;

  font-size: 11.5px;
  font-weight: 500;
}

/* =========================================================
   EQUIPAMENTO
   ========================================================= */

.equipment-card {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 11px;

  min-width: 0;
  padding: 12px;

  border: 1px solid #e2e8f0;
  border-radius: 10px;

  background: #fafbfd;
  color: inherit;

  text-decoration: none;

  transition:
    background-color 0.15s ease,
    border-color 0.15s ease,
    transform 0.15s ease,
    box-shadow 0.15s ease;
}

.equipment-card:hover {
  border-color: #cfd9e8;

  background: #f6f8fc;

  box-shadow: 0 3px 10px rgb(34 55 87 / 5%);

  transform: translateY(-1px);
}

.equipment-icon {
  display: grid;
  width: 34px;
  height: 34px;
  place-items: center;

  border-radius: 8px;

  background: #edf2f8;
  color: #385b86;
}

.equipment-content {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 3px;
}

.equipment-label {
  color: #8b97a9;

  font-size: 9px;
  font-weight: 750;

  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.equipment-name {
  overflow: hidden;

  color: #304d73;

  font-size: 11.5px;
  font-weight: 700;
  line-height: 1.35;

  text-overflow: ellipsis;
  white-space: nowrap;
}

.equipment-arrow {
  flex: 0 0 auto;

  color: #8c9aae;

  transition:
    color 0.15s ease,
    transform 0.15s ease;
}

.equipment-card:hover .equipment-arrow {
  color: #385b86;

  transform: translateX(2px);
}

.equipment-card--disabled {
  cursor: default;
  opacity: 0.7;
}

.equipment-card--disabled:hover {
  border-color: #e2e8f0;

  background: #fafbfd;

  box-shadow: none;

  transform: none;
}

/* =========================================================
   RESPONSIVIDADE
   ========================================================= */

@media (max-width: 620px) {
  .startup-date-row {
    align-items: flex-start;
    flex-direction: column;
    gap: 10px;
  }

  .startup-date {
    font-size: 25px;
  }

  .equipment-name {
    white-space: normal;
  }
}
</style>
