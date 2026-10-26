<script setup lang="ts">
import { Boxes, Info, Layers, Package, Plus, Upload } from "lucide-vue-next";
import Button from "~/components/ui/Button.vue";
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
  <header class="master-hero">
    <div class="master-hero__copy">
      <p class="eyebrow">Administração · Equipamentos</p>
      <h1>Catálogo Mestre</h1>
      <p class="master-hero__description">
        Modelos reutilizáveis de equipamentos para novas obras, organizados por área e
        componentes opcionais.
      </p>
      <ul class="master-facts" aria-label="Resumo do catálogo">
        <li>
          <Package :size="15" aria-hidden="true" />
          <span>{{ plural(props.equipmentCount, "equipamento", "equipamentos") }}</span>
        </li>
        <li>
          <Layers :size="15" aria-hidden="true" />
          <span>{{ plural(props.areaCount, "área ativa", "áreas ativas") }}</span>
        </li>
        <li>
          <Boxes :size="15" aria-hidden="true" />
          <span>{{ plural(props.componentCount, "componente", "componentes") }}</span>
        </li>
        <li v-if="props.activeEquipmentCount !== props.equipmentCount" class="fact-muted">
          {{ props.activeEquipmentCount }} ativo{{ props.activeEquipmentCount === 1 ? "" : "s" }}
        </li>
      </ul>
    </div>

    <div class="master-hero__actions">
      <Button
        variant="outline"
        class="header-action"
        :disabled="props.busy"
        @click="emit('manageAreas')"
      >
        <Layers aria-hidden="true" /> Gerenciar áreas
      </Button>
      <Button
        variant="outline"
        class="header-action"
        :disabled="props.busy"
        @click="emit('importSeed')"
      >
        <Upload aria-hidden="true" /> Importar seed
      </Button>
      <Button class="header-action" :disabled="props.busy" @click="emit('create')">
        <Plus aria-hidden="true" /> Novo equipamento
      </Button>
    </div>
  </header>

  <div class="scope-note">
    <Info :size="16" aria-hidden="true" />
    <p>
      Alterações aqui valem apenas para novas obras. Equipamentos e EAP de obras já
      criadas não são modificados.
    </p>
  </div>
</template>

<style scoped>
.master-hero {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
  padding: 4px 0 2px;
}

.master-hero__copy {
  min-width: 0;
}

.eyebrow {
  margin: 0 0 6px;
  color: #2e5aac;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.master-hero h1 {
  margin: 0;
  color: #20324a;
  font-size: clamp(28px, 3vw, 36px);
  font-weight: 800;
  line-height: 1.08;
  letter-spacing: -0.02em;
}

.master-hero__description {
  max-width: 720px;
  margin: 8px 0 0;
  color: #6d7c92;
  font-size: 14px;
  line-height: 1.55;
}

.master-facts {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
  margin: 14px 0 0;
  padding: 0;
  list-style: none;
}

.master-facts li {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #64748b;
  font-size: 12px;
  font-weight: 600;
}

.master-facts svg {
  color: #5479aa;
}

.fact-muted {
  color: #8a97a9 !important;
  font-size: 11px !important;
}

.master-hero__actions {
  display: flex;
  flex-wrap: wrap;
  flex: 0 0 auto;
  justify-content: flex-end;
  gap: 8px;
}

.scope-note {
  display: flex;
  align-items: flex-start;
  gap: 9px;
  border: 1px solid #dbe7f5;
  border-radius: 12px;
  padding: 10px 13px;
  background: #f7faff;
  color: #4b6584;
  font-size: 12px;
  line-height: 1.5;
}

.scope-note svg {
  flex: 0 0 auto;
  margin-top: 1px;
  color: #3f6ea5;
}

.scope-note p {
  margin: 0;
}

@media (max-width: 820px) {
  .master-hero {
    align-items: flex-start;
    flex-direction: column;
    gap: 14px;
  }

  .master-hero__actions {
    width: 100%;
    justify-content: flex-start;
  }

  .header-action {
    flex: 1 1 150px;
  }
}

@media (max-width: 560px) {
  .header-action {
    flex-basis: 100%;
  }
}
</style>
