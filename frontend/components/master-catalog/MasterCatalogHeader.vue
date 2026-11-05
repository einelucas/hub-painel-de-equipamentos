<script setup lang="ts">
import { mdiLayersOutline, mdiPlus, mdiUpload } from "@mdi/js";
import { Boxes, Info, Layers3, Package } from "lucide-vue-next";
import { VBtn } from "vuetify/components";
import { plural } from "~/utils/masterCatalog";

const props = defineProps<{
  equipmentCount: number;
  activeEquipmentCount: number;
  areaCount: number;
  componentCount: number;
  busy: boolean;
}>();
const emit = defineEmits<{
  create: [];
  manageAreas: [];
  importSeed: [];
}>();
</script>

<template>
  <header class="catalog-header">
    <div class="header-title">
      <p class="eyebrow">Administração <span aria-hidden="true">/</span> Equipamentos</p>
      <h1>Catálogo Mestre</h1>
      <p class="header-subtitle">Gerencie modelos de equipamentos e onde poderão ser usados em novas obras.</p>
    </div>
    <div class="header-actions">
      <VBtn
        variant="outlined"
        color="secondary"
        size="small"
        :prepend-icon="mdiLayersOutline"
        :disabled="props.busy"
        @click="emit('manageAreas')"
      >Gerenciar áreas</VBtn>
      <VBtn
        variant="outlined"
        color="secondary"
        size="small"
        :prepend-icon="mdiUpload"
        :disabled="props.busy"
        @click="emit('importSeed')"
      >Importar seed</VBtn>
      <VBtn
        variant="flat"
        color="primary"
        size="small"
        :prepend-icon="mdiPlus"
        :disabled="props.busy"
        @click="emit('create')"
      >Novo equipamento</VBtn>
    </div>
  </header>

  <div class="catalog-overview" aria-label="Resumo do catálogo">
    <div class="overview-item">
      <Package :size="17" aria-hidden="true" />
      <span>{{ plural(props.equipmentCount, "equipamento", "equipamentos") }}</span>
    </div>
    <div class="overview-item">
      <Layers3 :size="17" aria-hidden="true" />
      <span>{{ plural(props.areaCount, "área ativa", "áreas ativas") }}</span>
    </div>
    <div class="overview-item">
      <Boxes :size="17" aria-hidden="true" />
      <span>{{ plural(props.componentCount, "componente", "componentes") }}</span>
    </div>
    <div v-if="props.activeEquipmentCount !== props.equipmentCount" class="overview-item overview-item--muted">
      {{ props.activeEquipmentCount }} ativo{{ props.activeEquipmentCount === 1 ? '' : 's' }}
    </div>
    <p class="overview-note"><Info :size="15" aria-hidden="true" /> Alterações no catálogo não modificam obras existentes.</p>
  </div>
</template>

<style scoped>
.catalog-header { display: flex; flex-wrap: wrap; align-items: flex-end; justify-content: space-between; gap: 16px 24px; padding: 4px 0 0; }
.header-title { min-width: 0; flex: 1 1 440px; }
.eyebrow { margin: 0 0 7px; color: #5477a4; font-size: 10.5px; font-weight: 800; letter-spacing: .09em; text-transform: uppercase; }
.eyebrow span { margin: 0 6px; color: #a3b2c4; }
.catalog-header h1 { margin: 0; color: #20324a; font-size: clamp(26px, 2.6vw, 33px); font-weight: 800; letter-spacing: -.035em; line-height: 1.12; }
.header-subtitle { max-width: 640px; margin: 7px 0 0; color: #6d7e95; font-size: 13px; line-height: 1.5; }
.header-actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 8px; }
.catalog-overview { display: flex; flex-wrap: wrap; align-items: center; gap: 9px 22px; border-bottom: 1px solid #e8edf3; padding: 12px 0 15px; }
.overview-item { display: inline-flex; align-items: center; gap: 6px; color: #60758e; font-size: 11.5px; font-weight: 650; }
.overview-item svg { color: #607ea4; }
.overview-item--muted { color: #929eac; }
.overview-note { display: inline-flex; flex-wrap: wrap; align-items: center; gap: 6px; margin: 0 0 0 auto; color: #8c99a8; font-size: 10.5px; }
.overview-note svg { flex-shrink: 0; }
@media (max-width: 920px) { .header-actions { justify-content: flex-start; } .overview-note { width: 100%; margin-left: 0; } }
@media (max-width: 500px) { .header-actions { width: 100%; } .header-actions :deep(.v-btn) { flex: 1 1 150px; } }
</style>
