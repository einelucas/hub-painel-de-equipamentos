<script setup lang="ts">
import { computed, ref, watch } from "vue";
import type { ProjectAdminTarget } from "~/types/equipment";

/**
 * Administração contextual da aba Equipamentos: configuração da obra
 * (ProjectContexts), os cadastros de apoio e o acesso por unidade.
 */
const props = defineProps<{ open: boolean; unitId: string }>();
const emit = defineEmits<{ close: []; changed: [] }>();

const auth = useAuthStore();
const section = ref("projects");
const catalog = ref("units");
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
  }
}

const CATALOGS = [
  { key: "units", label: "Unidades" },
  { key: "areas", label: "Árvore EAP" },
  { key: "disciplines", label: "Disciplinas" },
  { key: "workPackages", label: "Work Packages" },
];

function onChanged(): void {
  emit("changed");
}

watch(
  () => props.unitId,
  (unitId) => {
    adminUnit.value = unitId;
  },
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
        <EapTreeAdmin
          v-else-if="catalog === 'areas'"
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
          <CatalogAdmin
            path="/work-packages"
            label="Work Packages"
            :has-code="true"
            :has-description="true"
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
</style>
