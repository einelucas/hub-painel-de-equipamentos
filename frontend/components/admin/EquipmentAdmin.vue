<script setup lang="ts">
import { computed, ref, watch } from "vue";
import type { AdminPanelSection } from "~/components/admin/AdminPanel.vue";
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

const CATALOGS = [
  { key: "units", label: "Unidades" },
  { key: "areas", label: "Árvore EAP" },
  { key: "disciplines", label: "Disciplinas" },
  { key: "criticalities", label: "Criticidades" },
  { key: "workPackages", label: "Work Packages" },
];

const sections = computed(() => {
  const items: AdminPanelSection[] = [];
  if (canManageCatalogs.value) items.push({ key: "projects", label: "Projetos", hint: "Obras de cada unidade" });
  if (canManageCatalogs.value) {
    items.push({
      key: "catalogs",
      label: "Catálogos",
      hint: "Cadastros usados nos equipamentos",
      children: CATALOGS,
      childTestId: "catalog-switch",
    });
  }
  if (canManageUsers.value) items.push({ key: "access", label: "Acesso às unidades", hint: "Quem enxerga cada unidade" });
  if (canManageUsers.value) items.push({ key: "notifications", label: "Notificações", hint: "Graph, regras e caixa de testes" });
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
    v-model:item="catalog"
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
          :has-color="true"
          @changed="onChanged"
        />
        <CatalogAdmin
          v-else-if="catalog === 'criticalities'"
          path="/criticality-labels"
          label="Criticidades"
          :has-code="false"
          :has-color="true"
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
      <NotificationCenter v-else-if="active === 'notifications'" />
    </template>
  </AdminPanel>
</template>
