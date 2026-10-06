<script setup lang="ts">
import { computed, ref, watch } from "vue";
import type { CatalogItem, CatalogList, ProjectAdminTarget } from "~/types/equipment";

/**
 * Administração contextual da aba Equipamentos: configuração da obra
 * (ProjectContexts), os cadastros de apoio e o acesso por unidade.
 */
const props = defineProps<{ open: boolean; unitId: string }>();
const emit = defineEmits<{ close: []; changed: [] }>();

const api = useApi();
const auth = useAuthStore();
const section = ref("projects");
const catalog = ref("units");
const contexts = ref<CatalogItem[]>([]);
const selectedContext = ref("");
/**
 * Unidade em administração: começa pela do filtro do módulo e é compartilhada
 * por Projetos e Catálogos dentro do painel, sem alterar o filtro global.
 */
const adminUnit = ref(props.unitId);

const canManageCatalogs = computed(() => auth.can("catalogs:manage"));
const canManageUsers = computed(() => auth.can("users:manage"));

const sections = computed(() => {
  const items: { key: string; label: string }[] = [];
  if (canManageCatalogs.value) items.push({ key: "projects", label: "Projetos" });
  if (canManageCatalogs.value) items.push({ key: "catalogs", label: "Catálogos" });
  if (canManageUsers.value) items.push({ key: "access", label: "Acesso às unidades" });
  return items;
});

// A seção ativa é sempre uma que o usuário pode ver (também quando o painel já nasce aberto).
watch(
  sections,
  (items) => {
    if (!items.some((item) => item.key === section.value)) section.value = items[0]?.key ?? "";
  },
  { immediate: true },
);

/** Ações contextuais de Projetos: só trocam para a seção/catálogo que já existe. */
function navigate(target: ProjectAdminTarget): void {
  section.value = target.section;
  if (target.section === "catalogs") {
    catalog.value = target.catalog;
    if (target.contextId) selectedContext.value = target.contextId;
  }
}

const CATALOGS = [
  { key: "units", label: "Unidades" },
  { key: "areas", label: "Áreas" },
  { key: "disciplines", label: "Disciplinas" },
  { key: "workPackages", label: "Work packages" },
];

const unitHint = computed(() =>
  adminUnit.value ? undefined : "Selecione uma unidade (filtro do módulo ou aba Projetos) para administrar este catálogo.",
);
const contextHint = computed(() => {
  if (!adminUnit.value) return unitHint.value;
  return selectedContext.value ? undefined : "Selecione um contexto de projeto acima.";
});

async function loadContexts(): Promise<void> {
  contexts.value = [];
  if (!adminUnit.value) return;
  contexts.value = (
    await api.get<CatalogList<CatalogItem>>(`/units/${adminUnit.value}/project-contexts`)
  ).items;
  if (!contexts.value.some((item) => item.id === selectedContext.value)) {
    selectedContext.value = contexts.value[0]?.id ?? "";
  }
}

function onChanged(): void {
  emit("changed");
  void loadContexts();
}

watch(
  () => props.unitId,
  (unitId) => {
    adminUnit.value = unitId;
  },
);

watch(
  () => [props.open, adminUnit.value],
  ([open]) => {
    if (open) void loadContexts();
  },
  { immediate: true },
);
</script>

<template>
  <AdminPanel
    v-model:section="section"
    :open="props.open"
    title="Administração · Equipamentos"
    description="Configuração das obras e cadastros de apoio aos equipamentos. Registros não são excluídos: use desativar."
    :sections="sections"
    @close="emit('close')"
  >
    <template #default="{ section: active }">
      <ProjectContextAdmin
        v-if="active === 'projects'"
        v-model:unit-id="adminUnit"
        @changed="onChanged"
        @navigate="navigate"
      />

      <template v-else-if="active === 'catalogs'">
        <nav class="catalog-switch" aria-label="Catálogos">
          <button
            v-for="item in CATALOGS"
            :key="item.key"
            type="button"
            :class="{ active: catalog === item.key }"
            :data-testid="`catalog-switch-${item.key}`"
            @click="catalog = item.key"
          >
            {{ item.label }}
          </button>
        </nav>

        <CatalogAdmin
          v-if="catalog === 'units'"
          path="/units"
          label="Unidades"
          :has-code="false"
          @changed="onChanged"
        />
        <CatalogAdmin
          v-else-if="catalog === 'areas'"
          path="/areas"
          label="Áreas"
          :has-code="false"
          :parent="{ unitId: adminUnit }"
          :query="{ unit_id: adminUnit }"
          :requires-parent="unitHint"
          @changed="onChanged"
        />
        <CatalogAdmin
          v-else-if="catalog === 'disciplines'"
          path="/disciplines"
          label="Disciplinas"
          :has-code="true"
          @changed="onChanged"
        />
        <template v-else>
          <label class="field context-picker">
            <span>Contexto de projeto</span>
            <select v-model="selectedContext" data-testid="wp-context">
              <option value="">Selecione</option>
              <option v-for="item in contexts" :key="item.id" :value="item.id">
                {{ item.code ? `${item.code} · ${item.name}` : item.name }}
              </option>
            </select>
          </label>
          <CatalogAdmin
            path="/work-packages"
            label="Work packages"
            :has-code="true"
            :parent="{ projectContextId: selectedContext }"
            :query="{ project_context_id: selectedContext }"
            :requires-parent="contextHint"
            @changed="onChanged"
          />
        </template>
      </template>

      <UnitAccessAdmin v-else-if="active === 'access'" @changed="emit('changed')" />
    </template>
  </AdminPanel>
</template>

<style scoped>
.catalog-switch { display: flex; flex-wrap: wrap; gap: 6px; padding-bottom: 12px; }
.catalog-switch button { border: 1px solid #e4e9f0; border-radius: 999px; padding: 5px 11px; background: #fff; color: #5d6b80; font-size: 11.5px; font-weight: 750; }
.catalog-switch button.active { border-color: #d5e2f3; background: #e8f1fc; color: #27456f; }
.catalog-switch button:focus-visible { outline: 2px solid #304f7e; outline-offset: 2px; }
.context-picker { padding-bottom: 12px; }
</style>
