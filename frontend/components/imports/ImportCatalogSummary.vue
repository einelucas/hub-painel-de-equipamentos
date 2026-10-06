<script setup lang="ts">
import { computed } from "vue";
import type { CatalogAction, CatalogItem, CatalogKind } from "~/types/imports";

/**
 * Catálogos do plano: o que já existe, o que será criado na importação, o que
 * conflita (bloqueia) e o que fica pendente (não bloqueia; vínculo vazio).
 * Nenhum cadastro prévio na Administração é exigido.
 */
const props = defineProps<{
  catalogs: CatalogItem[];
  responsibles?: { resolved: number; unresolved: number };
}>();

const KINDS: { key: CatalogKind; label: string }[] = [
  { key: "eap_node", label: "EAP / Localização" },
  { key: "project_eap", label: "EAP vinculada à obra" },
  { key: "discipline", label: "Disciplina" },
  { key: "work_package", label: "Work Package" },
  { key: "supplier", label: "Fornecedor" },
];

const ACTION_LABELS: Record<CatalogAction, string> = {
  EXISTING: "Existente",
  CREATE: "Novo — será criado",
  CONFLICT: "Conflito",
  UNRESOLVED: "Pendente",
};

const ACTION_ORDER: CatalogAction[] = ["CONFLICT", "CREATE", "UNRESOLVED", "EXISTING"];

const EVIDENCE_LABELS: Record<string, string> = {
  OFFICIAL_CATALOG: "catálogo oficial",
  MONDAY: "Monday",
  LGE: "LGE",
  MANUAL_MAPPING: "mapeamento manual",
};

const sections = computed(() =>
  KINDS.map((kind) => {
    const items = props.catalogs
      .filter((item) => item.kind === kind.key)
      .sort((a, b) => ACTION_ORDER.indexOf(a.action) - ACTION_ORDER.indexOf(b.action) || a.label.localeCompare(b.label));
    const counts = Object.fromEntries(ACTION_ORDER.map((action) => [action, items.filter((i) => i.action === action).length]));
    return { ...kind, items, counts: counts as Record<CatalogAction, number> };
  }).filter((section) => section.items.length > 0),
);

function evidence(item: CatalogItem): string | null {
  return item.evidenceSource ? EVIDENCE_LABELS[item.evidenceSource] ?? item.evidenceSource : null;
}
</script>

<template>
  <section class="catalogs" data-testid="plan-catalogs" aria-label="Catálogos da importação">
    <h4>Catálogos</h4>
    <p class="catalogs-hint">
      Itens novos são criados na própria importação, na mesma transação. Conflitos bloqueiam o equipamento;
      pendências não bloqueiam — o equipamento é importado sem o vínculo e o valor original fica preservado.
    </p>

    <details v-for="section in sections" :key="section.key" class="catalog-kind" :data-testid="`catalog-${section.key}`">
      <summary>
        <strong>{{ section.label }}</strong>
        <span
v-for="action in ACTION_ORDER" v-show="section.counts[action] > 0" :key="action"
          :class="['badge', `badge--${action.toLowerCase()}`]" :data-testid="`catalog-${section.key}-${action}`">
          {{ ACTION_LABELS[action] }}: {{ section.counts[action] }}
        </span>
      </summary>
      <ul>
        <li v-for="item in section.items" :key="`${item.kind}-${item.key}`">
          <span class="catalog-label" :title="item.label">{{ item.label }}</span>
          <span :class="['badge', `badge--${item.action.toLowerCase()}`]">{{ ACTION_LABELS[item.action] }}</span>
          <small v-if="evidence(item)" class="catalog-meta">fonte: {{ evidence(item) }}</small>
          <small v-if="item.message && item.action !== 'EXISTING'" class="catalog-meta">{{ item.message }}</small>
        </li>
      </ul>
    </details>

    <div v-if="responsibles" class="catalog-kind catalog-kind--flat" data-testid="catalog-responsibles">
      <strong>Responsável</strong>
      <span class="badge badge--existing">Usuário encontrado: {{ responsibles.resolved }}</span>
      <span v-if="responsibles.unresolved" class="badge badge--unresolved">
        Pendente — importado sem responsável: {{ responsibles.unresolved }}
      </span>
    </div>
  </section>
</template>

<style scoped>
.catalogs { display: grid; gap: 6px; border: 1px solid #e4e9f0; border-radius: 10px; padding: 10px 12px; }
.catalogs h4 { margin: 0; color: #2b3e58; font-size: 12px; font-weight: 800; }
.catalogs-hint { margin: 0; color: #8b96a5; font-size: 11.5px; }
.catalog-kind { border-top: 1px solid #f0f3f7; padding-top: 6px; font-size: 12px; color: #2b3e58; }
.catalog-kind summary { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; cursor: pointer; }
.catalog-kind--flat { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }
.catalog-kind ul { display: grid; gap: 4px; margin: 6px 0 0; padding: 0; list-style: none; max-height: 180px; overflow-y: auto; }
.catalog-kind li { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }
.catalog-label { min-width: 0; overflow: hidden; font-weight: 700; text-overflow: ellipsis; white-space: nowrap; max-width: 60%; }
.catalog-meta { color: #7a879a; font-size: 11px; }
.badge { border-radius: 999px; padding: 1px 8px; font-size: 10.5px; font-weight: 800; }
.badge--existing { background: #eaf3e6; color: #477a32; }
.badge--create { background: #e8f0fb; color: #2d5c9a; }
.badge--conflict { background: #fbeeed; color: #a4453a; }
.badge--unresolved { background: #fdf6e7; color: #8a5a12; }
@media (max-width: 620px) { .catalog-label { max-width: 100%; } }
</style>
