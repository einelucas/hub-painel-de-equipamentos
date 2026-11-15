<script setup lang="ts">
import { VTable, VTextField } from "vuetify/components";
import type { StartupItem, StartupItemInput } from "~/types/startupSimulation";
import { formatScenarioDate } from "~/utils/startupSimulation";

defineProps<{
  entries: Array<{ row: StartupItem; index: number }>;
  editable: boolean;
  loading?: boolean;
}>();
const emit = defineEmits<{
  "edit-number": [index: number, field: "suppliesDays" | "legalDays" | "manufactureDays" | "preStartDays", value: unknown];
  "edit-startup": [index: number, value: string];
}>();
const inputCols: Array<{ field: "suppliesDays" | "legalDays" | "manufactureDays" | "preStartDays"; label: string }> = [
  { field: "suppliesDays", label: "Suprimentos" },
  { field: "legalDays", label: "Jurídico" },
  { field: "manufactureDays", label: "Fabricação" },
  { field: "preStartDays", label: "Antecedência" },
];
function numberAt(row: StartupItemInput, key: keyof StartupItemInput) {
  return row[key] === null ? "" : String(row[key]);
}
</script>

<template>
  <div class="startup-table-scroll">
    <VTable density="compact" class="startup-table">
      <thead>
        <tr>
          <th class="equipment-col">Equipamento</th>
          <th>Disciplina / Fornecedor</th>
          <th>Startup próprio</th>
          <th v-for="column in inputCols" :key="column.field">{{ column.label }} (dias)</th>
          <th>Limite negociação</th>
          <th>Limite contrato/OC</th>
          <th>Limite entrega</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="{ row, index } in entries" :key="row.id">
          <td class="equipment-col">
            <strong>{{ row.name }}</strong>
            <span v-if="row.area" class="secondary">{{ row.area }}</span>
          </td>
          <td>
            <span>{{ row.discipline || "—" }}</span>
            <span class="secondary">{{ row.supplier || "Sem fornecedor" }}</span>
          </td>
          <td>
            <VTextField
              :model-value="row.startupAt ?? ''"
              type="date"
              density="compact"
              hide-details
              variant="outlined"
              :disabled="!editable || loading"
              :aria-label="`Startup próprio de ${row.name} (vazio herda cenário)`"
              @update:model-value="emit('edit-startup', index, String($event ?? ''))"
            />
          </td>
          <td v-for="column in inputCols" :key="column.field">
            <VTextField
              :model-value="numberAt(row, column.field)"
              type="number"
              min="0"
              max="36500"
              step="1"
              density="compact"
              hide-details
              variant="outlined"
              :disabled="!editable || loading"
              :aria-label="`${column.label} de ${row.name}`"
              @update:model-value="emit('edit-number', index, column.field, $event)"
            />
          </td>
          <td class="date-col">{{ formatScenarioDate(row.negotiationDeadline) }}</td>
          <td class="date-col">{{ formatScenarioDate(row.contractDeadline) }}</td>
          <td class="date-col">{{ formatScenarioDate(row.deliveryDeadline) }}</td>
        </tr>
        <tr v-if="!entries.length"><td colspan="10" class="empty">Nenhum equipamento atende ao filtro selecionado.</td></tr>
      </tbody>
    </VTable>
  </div>
</template>

<style scoped>
.startup-table-scroll { max-width: 100%; max-height: 570px; overflow: auto; border: 1px solid #e6ebf2; border-radius: 11px; }
.startup-table { min-width: 1480px; font-size: 11.5px; color: #31435c; }
.startup-table :deep(th) { white-space: nowrap; position: sticky; top: 0; background: #f6f8fb; color: #617087; font-weight: 750; z-index: 2; }
.startup-table :deep(td) { padding: 9px 10px; border-bottom: 1px solid #edf1f5; vertical-align: middle; }
.startup-table .equipment-col { min-width: 245px; max-width: 300px; }
.startup-table td:nth-child(2) { min-width: 170px; }
.startup-table td:nth-child(3) { min-width: 155px; }
.startup-table td:nth-child(n+4):nth-child(-n+7) { min-width: 117px; }
.startup-table .secondary { display: block; margin-top: 3px; font-size: 10px; color: #8897aa; }
.startup-table .date-col { font-variant-numeric: tabular-nums; white-space: nowrap; font-weight: 650; }
.startup-table .empty { text-align: center; padding: 24px; color: #8290a3; }
.startup-table :deep(.v-field__input) { min-height: 36px; padding-top: 5px; padding-bottom: 5px; font-size: 11px; }
</style>
