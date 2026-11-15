<script setup lang="ts">
import { mdiDeleteOutline } from "@mdi/js";
import { VBtn, VCombobox, VTable, VTextField } from "vuetify/components";
import type { StartupItem, StartupItemInput } from "~/types/startupSimulation";
import { formatScenarioDate } from "~/utils/startupSimulation";

defineProps<{
  entries: Array<{ row: StartupItem; index: number }>;
  editable: boolean;
  loading?: boolean;
}>();
type TextField = "origin" | "discipline" | "name" | "supplier" | "area" | "responsible";
type DaysField = "suppliesDays" | "legalDays" | "manufactureDays" | "preStartDays";
const emit = defineEmits<{
  "edit-text": [index: number, field: TextField, value: string];
  "edit-number": [index: number, field: DaysField, value: unknown];
  "edit-startup": [index: number, value: string];
  remove: [index: number];
}>();
const dayColumns: Array<{ field: DaysField; label: string }> = [
  { field: "suppliesDays", label: "Suprimentos" },
  { field: "legalDays", label: "Jurídico" },
  { field: "manufactureDays", label: "Fabricação" },
  { field: "preStartDays", label: "Antecedência" },
];
function numberAt(row: StartupItemInput, key: DaysField): string {
  return row[key] === null ? "" : String(row[key]);
}
function textAt(row: StartupItemInput, key: TextField): string {
  return row[key] ?? "";
}
</script>

<template>
  <div class="startup-table-scroll">
    <VTable density="compact" class="startup-table">
      <thead>
        <tr>
          <th class="equipment-col">Nome / Origem</th>
          <th>Disciplina / Fornecedor</th>
          <th>Área / Responsável</th>
          <th>Startup próprio</th>
          <th v-for="column in dayColumns" :key="column.field">{{ column.label }} (dias)</th>
          <th>Limite negociação</th>
          <th>Limite contrato/OC</th>
          <th>Limite entrega</th>
          <th v-if="editable" class="actions-col">Ações</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="{ row, index } in entries" :key="row.id">
          <td class="equipment-col">
            <div class="stacked-fields">
              <VTextField
                :model-value="row.name"
                label="Nome"
                maxlength="500"
                density="compact"
                hide-details
                variant="outlined"
                :disabled="!editable || loading"
                :aria-label="`Nome do equipamento da linha ${index + 1}`"
                @update:model-value="emit('edit-text', index, 'name', String($event ?? ''))"
              />
              <VCombobox
                :model-value="row.origin ?? ''"
                :items="['Nacional', 'Importado']"
                label="Origem"
                maxlength="160"
                density="compact"
                hide-details
                variant="outlined"
                :disabled="!editable || loading"
                :aria-label="`Origem de ${row.name}`"
                @update:model-value="emit('edit-text', index, 'origin', String($event ?? ''))"
              />
            </div>
          </td>
          <td>
            <div class="stacked-fields">
              <VTextField
                :model-value="textAt(row, 'discipline')"
                label="Disciplina"
                maxlength="160"
                density="compact"
                hide-details
                variant="outlined"
                :disabled="!editable || loading"
                :aria-label="`Disciplina de ${row.name}`"
                @update:model-value="emit('edit-text', index, 'discipline', String($event ?? ''))"
              />
              <VTextField
                :model-value="textAt(row, 'supplier')"
                label="Fornecedor"
                maxlength="200"
                density="compact"
                hide-details
                variant="outlined"
                :disabled="!editable || loading"
                :aria-label="`Fornecedor de ${row.name}`"
                @update:model-value="emit('edit-text', index, 'supplier', String($event ?? ''))"
              />
            </div>
          </td>
          <td>
            <div class="stacked-fields">
              <VTextField
                :model-value="textAt(row, 'area')"
                label="Área"
                maxlength="160"
                density="compact"
                hide-details
                variant="outlined"
                :disabled="!editable || loading"
                :aria-label="`Área de ${row.name}`"
                @update:model-value="emit('edit-text', index, 'area', String($event ?? ''))"
              />
              <VTextField
                :model-value="textAt(row, 'responsible')"
                label="Responsável"
                maxlength="160"
                density="compact"
                hide-details
                variant="outlined"
                :disabled="!editable || loading"
                :aria-label="`Responsável por ${row.name}`"
                @update:model-value="emit('edit-text', index, 'responsible', String($event ?? ''))"
              />
            </div>
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
          <td v-for="column in dayColumns" :key="column.field">
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
          <td class="date-col" :aria-label="`Negociação calculada de ${row.name}`">
            {{ formatScenarioDate(row.negotiationDeadline) }}
          </td>
          <td class="date-col" :aria-label="`Contrato calculado de ${row.name}`">
            {{ formatScenarioDate(row.contractDeadline) }}
          </td>
          <td class="date-col" :aria-label="`Entrega calculada de ${row.name}`">
            {{ formatScenarioDate(row.deliveryDeadline) }}
          </td>
          <td v-if="editable">
            <VBtn
              :icon="mdiDeleteOutline" variant="text" color="error" size="x-small"
              :aria-label="`Remover ${row.name} do cenário`" :disabled="loading"
              @click="emit('remove', index)"
            />
          </td>
        </tr>
        <tr v-if="!entries.length">
          <td :colspan="editable ? 12 : 11" class="empty">
            Nenhum equipamento neste cenário ou nenhum resultado para o filtro selecionado.
          </td>
        </tr>
      </tbody>
    </VTable>
  </div>
</template>

<style scoped>
.startup-table-scroll { max-width: 100%; max-height: 590px; overflow: auto; border: 1px solid #e6ebf2; border-radius: 11px; }
.startup-table { min-width: 1760px; font-size: 11.5px; color: #31435c; }
.startup-table :deep(th) { white-space: nowrap; position: sticky; top: 0; background: #f6f8fb; color: #617087; font-weight: 750; z-index: 2; }
.startup-table :deep(td) { padding: 9px 10px; border-bottom: 1px solid #edf1f5; vertical-align: middle; }
.startup-table .equipment-col { min-width: 255px; }
.startup-table td:nth-child(2), .startup-table td:nth-child(3) { min-width: 210px; }
.startup-table td:nth-child(4) { min-width: 155px; }
.startup-table td:nth-child(n+5):nth-child(-n+8) { min-width: 120px; }
.startup-table .stacked-fields { display: grid; gap: 7px; min-width: 170px; }
.startup-table .date-col { font-variant-numeric: tabular-nums; white-space: nowrap; font-weight: 650; }
.startup-table .empty { text-align: center; padding: 24px; color: #8290a3; }
.startup-table :deep(.v-field__input) { min-height: 36px; padding-top: 5px; padding-bottom: 5px; font-size: 11px; }
.startup-table :deep(.v-label) { font-size: 11px; }
</style>
