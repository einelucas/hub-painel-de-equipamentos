<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { mdiClose, mdiMagnify } from "@mdi/js";
import {
  VBtn,
  VCard,
  VCardActions,
  VCardText,
  VCardTitle,
  VCheckbox,
  VDialog,
  VTextField,
} from "vuetify/components";
import type { CatalogItem } from "~/types/equipment";

const props = withDefaults(
  defineProps<{
    open: boolean;
    unitName: string;
    projects: CatalogItem[];
    initialSelectedId?: string;
  }>(),
  { initialSelectedId: "" },
);
const emit = defineEmits<{
  close: [];
  generate: [projectIds: string[]];
}>();

const selectedIds = ref<string[]>([]);
const search = ref<string | null>("");

const availableProjects = computed(() =>
  props.projects
    .filter((project) => project.active)
    .slice()
    .sort((a, b) => a.name.localeCompare(b.name, "pt-BR")),
);
const visibleProjects = computed(() => {
  const query = (search.value ?? "").trim().toLocaleLowerCase("pt-BR");
  return query
    ? availableProjects.value.filter((project) =>
        [project.name, project.code ?? ""]
          .join(" ")
          .toLocaleLowerCase("pt-BR")
          .includes(query),
      )
    : availableProjects.value;
});
const allSelected = computed(
  () =>
    availableProjects.value.length > 0 &&
    availableProjects.value.every((project) => selectedIds.value.includes(project.id)),
);

watch(
  () => props.open,
  (open) => {
    if (!open) return;
    const selected = availableProjects.value.some(
      (project) => project.id === props.initialSelectedId,
    );
    selectedIds.value = selected ? [props.initialSelectedId] : [];
    search.value = "";
  },
  { immediate: true },
);

function toggleProject(id: string, checked: boolean): void {
  if (!availableProjects.value.some((project) => project.id === id)) return;
  selectedIds.value = checked
    ? [...new Set([...selectedIds.value, id])]
    : selectedIds.value.filter((value) => value !== id);
}

function toggleAll(): void {
  selectedIds.value = allSelected.value
    ? []
    : availableProjects.value.map((project) => project.id);
}

function generate(): void {
  // Só IDs que ainda pertencem às opções válidas da unidade podem ser enviados.
  const allowedIds = new Set(availableProjects.value.map((project) => project.id));
  const ids = [...new Set(selectedIds.value)].filter((id) => allowedIds.has(id));
  if (!ids.length) return;
  emit("generate", ids);
}
</script>

<template>
  <VDialog
    :model-value="open"
    max-width="600"
    aria-labelledby="report-project-title"
    aria-describedby="report-project-description"
    @update:model-value="(value) => { if (!value) emit('close'); }"
  >
    <VCard rounded="lg" class="report-project-card">
      <VCardTitle class="report-project-header">
        <div class="report-project-heading">
          <h2 id="report-project-title">Selecionar obras do relatório</h2>
          <span>{{ unitName }}</span>
        </div>
        <VBtn
          variant="text"
          density="comfortable"
          :icon="mdiClose"
          aria-label="Fechar seleção de obras"
          @click="emit('close')"
        />
      </VCardTitle>

      <VCardText class="report-project-body">
        <p id="report-project-description" class="report-project-description">
          Selecione uma ou mais obras para consolidar no relatório executivo.
          Os dados serão consultados integralmente, sem os filtros da tabela.
        </p>
        <VTextField
          v-model="search"
          :prepend-inner-icon="mdiMagnify"
          label="Buscar obra"
          placeholder="Nome ou código"
          variant="outlined"
          density="compact"
          hide-details
          clearable
          data-testid="report-project-search"
        />
        <div class="report-project-toolbar">
          <span data-testid="report-selected-count">
            {{ selectedIds.length }} de {{ availableProjects.length }} selecionada(s)
          </span>
          <VBtn
            variant="text"
            color="primary"
            size="small"
            :disabled="!availableProjects.length"
            data-testid="report-select-all"
            @click="toggleAll"
          >
            {{ allSelected ? "Limpar seleção" : "Selecionar todas" }}
          </VBtn>
        </div>
        <div class="report-project-options" role="group" aria-label="Obras disponíveis">
          <VCheckbox
            v-for="project in visibleProjects"
            :key="project.id"
            :model-value="selectedIds.includes(project.id)"
            :label="project.code ? project.code + ' · ' + project.name : project.name"
            color="primary"
            density="comfortable"
            hide-details
            :data-testid="'report-project-' + project.id"
            @update:model-value="(checked) => toggleProject(project.id, Boolean(checked))"
          />
          <p v-if="!visibleProjects.length" class="report-project-empty">
            {{ availableProjects.length ? "Nenhuma obra encontrada na busca." : "Nenhuma obra disponível nesta unidade." }}
          </p>
        </div>
      </VCardText>
      <VCardActions class="report-project-actions">
        <VBtn variant="outlined" color="secondary" @click="emit('close')">
          Cancelar
        </VBtn>
        <VBtn
          variant="flat"
          color="primary"
          :disabled="selectedIds.length === 0"
          data-testid="report-project-generate"
          @click="generate"
        >
          Gerar relatório ({{ selectedIds.length }})
        </VBtn>
      </VCardActions>
    </VCard>
  </VDialog>
</template>

<style scoped>
.report-project-card { color: #213758; }
.report-project-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 20px 20px 12px;
  white-space: normal;
}
.report-project-heading { display: grid; gap: 5px; }
.report-project-heading h2 { margin: 0; font-size: 18px; font-weight: 700; }
.report-project-heading span { color: #697a90; font-size: 13px; }
.report-project-body { display: grid; gap: 14px; padding: 12px 20px; }
.report-project-description { margin: 0; color: #53657c; font-size: 13px; line-height: 1.5; }
.report-project-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 10px; color: #65768d; font-size: 12px; }
.report-project-options { max-height: 260px; overflow: auto; border: 1px solid #e0e7ef; border-radius: 10px; padding: 4px 12px; }
.report-project-empty { margin: 12px 0; color: #697a90; font-size: 13px; }
.report-project-actions { justify-content: flex-end; gap: 10px; padding: 14px 20px 20px; }
@media (max-width: 480px) {
  .report-project-header { padding: 16px 16px 10px; }
  .report-project-body { padding: 10px 16px; }
  .report-project-actions { flex-wrap: wrap; padding: 12px 16px 16px; }
}
</style>
