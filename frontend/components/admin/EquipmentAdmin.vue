<script setup lang="ts">
import { computed, ref, watch } from "vue";
import type { CatalogItem, CatalogList } from "~/types/equipment";

/**
 * Administração contextual da aba Equipamentos: só os cadastros que dão
 * suporte a criar/classificar um equipamento, mais o acesso por unidade.
 */
const props = defineProps<{ open: boolean; unitId: string }>();
const emit = defineEmits<{ close: []; changed: [] }>();

const api = useApi();
const auth = useAuthStore();
const section = ref("catalogs");
const catalog = ref("units");
const contexts = ref<CatalogItem[]>([]);
const selectedContext = ref("");

const canManageCatalogs = computed(() => auth.can("catalogs:manage"));
const canManageUsers = computed(() => auth.can("users:manage"));

const sections = computed(() => {
  const items: { key: string; label: string }[] = [];
  if (canManageCatalogs.value) items.push({ key: "catalogs", label: "Catálogos" });
  if (canManageUsers.value) items.push({ key: "access", label: "Acesso às unidades" });
  return items;
});

const CATALOGS = [
  { key: "units", label: "Unidades" },
  { key: "contexts", label: "Contextos de projeto" },
  { key: "areas", label: "Áreas" },
  { key: "disciplines", label: "Disciplinas" },
  { key: "workPackages", label: "Work packages" },
];

const unitHint = computed(() =>
  props.unitId ? undefined : "Selecione uma unidade no filtro do módulo para administrar este catálogo.",
);
const contextHint = computed(() => {
  if (!props.unitId) return unitHint.value;
  return selectedContext.value ? undefined : "Selecione um contexto de projeto acima.";
});

async function loadContexts(): Promise<void> {
  contexts.value = [];
  if (!props.unitId) return;
  contexts.value = (
    await api.get<CatalogList<CatalogItem>>(`/units/${props.unitId}/project-contexts`)
  ).items;
  if (!contexts.value.some((item) => item.id === selectedContext.value)) {
    selectedContext.value = contexts.value[0]?.id ?? "";
  }
}

function onChanged(): void {
  emit("changed");
  if (catalog.value === "contexts") void loadContexts();
}

watch(
  () => [props.open, props.unitId],
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
    description="Cadastros de apoio à criação e classificação de equipamentos. Registros não são excluídos: use desativar."
    :sections="sections"
    @close="emit('close')"
  >
    <template #default="{ section: active }">
      <template v-if="active === 'catalogs'">
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
          :has-code="true"
          @changed="onChanged"
        />
        <CatalogAdmin
          v-else-if="catalog === 'contexts'"
          :path="props.unitId ? `/units/${props.unitId}/project-contexts` : '/units'"
          label="Contextos"
          :has-code="true"
          :requires-parent="unitHint"
          @changed="onChanged"
        />
        <CatalogAdmin
          v-else-if="catalog === 'areas'"
          path="/areas"
          label="Áreas"
          :has-code="false"
          :parent="{ unitId: props.unitId }"
          :query="{ unit_id: props.unitId }"
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
                {{ item.code }} · {{ item.name }}
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
