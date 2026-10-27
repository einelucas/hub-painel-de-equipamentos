<script setup lang="ts">
import { computed } from "vue";
import Button from "~/components/ui/Button.vue";
import ImportCatalogSummary from "~/components/imports/ImportCatalogSummary.vue";
import SupplierCombobox from "~/components/imports/SupplierCombobox.vue";
import { useImportState } from "~/composables/useImportState";

/**
 * Passo 4: plano do motor + confirmação explícita. Com item BLOCKED (ou mapping
 * inválido) o botão de confirmar fica desabilitado; nada é aplicado automaticamente.
 */
const {
  plan,
  batches,
  totals: sourceTotals,
  selectedContext,
  suppliers,
  mappingDirty,
  busy,
  stale,
  apply,
  buildPlan,
  setSupplierSelection,
  step,
} = useImportState();

const totals = computed(() => {
  const groups = plan.value?.groups ?? [];
  return {
    create: groups.reduce((sum, group) => sum + group.create, 0),
    update: groups.reduce((sum, group) => sum + group.update, 0),
    noop: groups.reduce((sum, group) => sum + group.noop, 0),
    blocked: groups.reduce((sum, group) => sum + group.blocked, 0),
  };
});

const catalogCreates = computed(() => (plan.value?.catalogs ?? []).filter((item) => item.action === "CREATE").length);
const equipmentWarnings = computed(() => plan.value?.equipmentWarnings ?? []);
const supplierSuggestions = computed(() => plan.value?.supplierSuggestions ?? []);

function selectionValue(item: (typeof supplierSuggestions.value)[number]): string {
  if (item.selectedAction === "NONE") return "__NONE__";
  return item.selectedSupplierId ?? "";
}

function useRecommended(item: (typeof supplierSuggestions.value)[number]): void {
  if (item.supplierId) setSupplierSelection(item.sourceKey, item.supplierId);
}

function useAllRecommended(): void {
  for (const item of supplierSuggestions.value) useRecommended(item);
}

const contextLabel = computed(() => {
  const context = selectedContext.value;
  if (!context) return "—";
  return context.code ? context.code + " · " + context.name : context.name;
});

const hasRecommendations = computed(() => supplierSuggestions.value.some((item) => item.supplierId));
</script>

<template>
  <div class="import-step" data-testid="import-step-plan">
    <p v-if="stale" class="callout callout--caution" role="alert" data-testid="import-stale">
      Os dados mudaram desde que o plano foi gerado. Gere o plano novamente antes de aplicar.
    </p>

    <template v-if="plan">
      <dl class="import-ledger" aria-label="Totais do plano">
        <div class="is-go"><dt>Criar</dt><dd>{{ totals.create }}</dd></div>
        <div><dt>Atualizar</dt><dd>{{ totals.update }}</dd></div>
        <div><dt>Sem alteração</dt><dd>{{ totals.noop }}</dd></div>
        <div :class="totals.blocked > 0 ? 'is-stop' : ''"><dt>Bloqueados</dt><dd data-testid="confirm-blocked">{{ totals.blocked }}</dd></div>
        <div><dt>Catálogos a criar</dt><dd data-testid="confirm-catalog-creates">{{ catalogCreates }}</dd></div>
      </dl>

      <table class="import-table">
        <thead><tr><th>Grupo</th><th class="num">Criar</th><th class="num">Atualizar</th><th class="num">Sem alteração</th><th class="num">Bloqueados</th></tr></thead>
        <tbody>
          <tr v-for="group in plan.groups" :key="group.name" :data-testid="`plan-group-${group.name}`">
            <td class="group-name">{{ group.name }}</td>
            <td class="num">{{ group.create }}</td>
            <td class="num">{{ group.update }}</td>
            <td class="num">{{ group.noop }}</td>
            <td class="num" :class="{ 'plan-blocked': group.blocked > 0 }">{{ group.blocked }}</td>
          </tr>
        </tbody>
      </table>

      <section v-if="plan.mappingIssues.length" class="callout callout--stop" data-testid="plan-mapping-issues">
        <h4>Mapeamento inválido</h4>
        <ul><li v-for="(issue, index) in plan.mappingIssues" :key="index">{{ issue.message }}</li></ul>
      </section>
      <section v-if="plan.blocked.length" class="callout callout--stop" data-testid="plan-blocked">
        <h4>Itens bloqueados <span class="import-count">({{ plan.blocked.length }})</span></h4>
        <ul>
          <li v-for="item in plan.blocked" :key="`${item.group}-${item.sourceKey}`">
            <strong>{{ item.group }} · {{ item.label }}</strong>
            <span v-for="issue in item.issues" :key="issue.code" class="issue-meta">{{ issue.message }}</span>
          </li>
        </ul>
      </section>

      <section class="import-panel" data-testid="plan-eap">
        <div class="import-panel-head"><h4>EAP dos equipamentos</h4></div>
        <ul class="eap-tally">
          <li>EAP identificada: <strong>{{ plan.eap.resolved }}</strong></li>
          <li>EAP nova (criada na importação): <strong>{{ plan.eap.create ?? 0 }}</strong></li>
          <li>Rótulo com nome de outro código (bloqueia): <strong>{{ plan.eap.conflict ?? 0 }}</strong></li>
          <li>Pendente — pai ou nome não comprovado (sem vínculo): <strong>{{ plan.eap.unresolved ?? 0 }}</strong></li>
          <li>Várias EAPs no valor (sem vínculo): <strong>{{ plan.eap.multiple }}</strong></li>
          <li>Sem código EAP (sem vínculo): <strong>{{ plan.eap.none }}</strong></li>
          <li>EAP fora do catálogo (sem vínculo): <strong>{{ plan.eap.notFound }}</strong></li>
        </ul>
      </section>
      <ImportCatalogSummary
        v-if="plan.catalogs?.length || plan.responsibles"
        :catalogs="plan.catalogs ?? []"
        :responsibles="plan.responsibles"
      />

      <section v-if="supplierSuggestions.length" class="import-panel supplier-review" data-testid="supplier-review">
        <div class="supplier-review-header">
          <div>
            <h4>Revisão de fornecedores</h4>
            <p>Correspondências exatas da origem vêm pré-selecionadas; recomendações históricas continuam sob sua revisão.</p>
          </div>
          <div class="supplier-review-actions">
            <button type="button" class="btn small" :disabled="!hasRecommendations" @click="useAllRecommended">
              Usar recomendado em todos
            </button>
            <NuxtLink class="btn small" to="/fornecedores">+ Cadastrar fornecedor</NuxtLink>
          </div>
        </div>
        <article v-for="item in supplierSuggestions" :key="item.sourceKey" class="supplier-suggestion">
          <div>
            <strong>{{ item.equipmentName }}</strong>
            <span>Origem: <span class="mono">{{ item.sourceValue ?? "não informado" }}</span></span>
            <span>
              Sugestão: {{ item.supplierName ?? "sem sugestão" }} · Confiança {{ item.confidence }}
            </span>
            <small v-for="evidence in item.evidence" :key="evidence">{{ evidence }}</small>
            <small v-if="item.requiresRegistration">Referência ainda não cadastrada como Supplier global.</small>
          </div>
          <div class="supplier-choice">
            <button
              type="button"
              class="recommended-button"
              :disabled="!item.supplierId"
              @click="useRecommended(item)"
            >
              Usar recomendado
            </button>
            <SupplierCombobox
              :model-value="selectionValue(item)"
              :suppliers="suppliers"
              :label="`Decisão de fornecedor para ${item.equipmentName}`"
              test-id="supplier-review-combobox"
              @update:model-value="setSupplierSelection(item.sourceKey, $event)"
            />
          </div>
        </article>
        <button v-if="mappingDirty" type="button" class="btn" :disabled="busy" :aria-busy="busy" @click="buildPlan">
          <span v-if="busy" class="spinner-small" aria-hidden="true" />
          {{ busy ? "Atualizando plano..." : "Atualizar plano com as decisões" }}
        </button>
      </section>

      <section v-if="equipmentWarnings.length" class="callout callout--caution" data-testid="plan-equipment-warnings">
        <h4>Pendências que não bloqueiam <span class="import-count">({{ equipmentWarnings.length }} equipamentos)</span></h4>
        <ul>
          <li v-for="item in equipmentWarnings" :key="item.sourceKey">
            <strong>{{ item.label }}</strong>
            <span v-for="issue in item.issues" :key="issue.code" class="issue-meta">{{ issue.message }}</span>
          </li>
        </ul>
      </section>
      <section v-if="plan.warnings.length" class="callout callout--caution">
        <h4>Avisos <span class="import-count">({{ plan.warnings.length }})</span></h4>
        <ul><li v-for="(warning, index) in plan.warnings" :key="index">{{ warning.message }}</li></ul>
      </section>

      <section class="confirm" data-testid="import-confirm-summary" aria-label="Resumo da importação">
        <span class="confirm-kicker">Será gravado em</span>
        <strong class="confirm-target">{{ contextLabel }}</strong>
        <dl>
          <div><dt>Arquivos</dt><dd data-testid="confirm-files">{{ batches.length }}</dd></div>
          <div><dt>Equipamentos</dt><dd>{{ sourceTotals.equipments }}</dd></div>
          <div><dt>Componentes</dt><dd>{{ sourceTotals.components }}</dd></div>
        </dl>
      </section>
    </template>

    <div class="import-actions">
      <Button variant="outline" :disabled="busy" @click="step = 'mapping'">Voltar ao mapeamento</Button>
      <Button
        variant="default"
        :disabled="!plan?.canApply || mappingDirty"
        :loading="busy"
        data-testid="import-confirm"
        @click="apply"
      >
        {{ busy ? "Importando..." : "Confirmar importação" }}
      </Button>
    </div>
  </div>
</template>

<style scoped>
.group-name { font-weight: 700; }
.plan-blocked { color: var(--stop); font-weight: 800; }

.callout { display: grid; gap: 8px; border-left: 3px solid; border-radius: 10px; padding: 11px 14px; }
.callout--stop { border-color: var(--stop); background: var(--stop-wash); }
.callout--caution { border-color: #d4a24c; background: var(--caution-wash); color: var(--caution); font-size: 12px; font-weight: 700; }
p.callout { margin: 0; }
.callout h4 { margin: 0; color: var(--ink); font-size: 12.5px; font-weight: 800; }
.callout ul { display: grid; margin: 0; padding: 0; gap: 6px; list-style: none; max-height: 220px; overflow-y: auto; color: var(--ink); font-size: 12px; font-weight: 500; }
.callout li { display: grid; gap: 1px; }
.issue-meta { color: var(--muted); font-size: 11px; }

.eap-tally { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); margin: 0; padding: 0; gap: 6px 18px; list-style: none; color: var(--muted); font-size: 12px; }
.eap-tally li { display: flex; justify-content: space-between; gap: 10px; border-bottom: 1px dotted var(--rule); padding-bottom: 5px; }
.eap-tally strong { color: var(--ink); font-family: var(--mono); font-variant-numeric: tabular-nums; }

.supplier-review { gap: 10px; }
.supplier-review-header { display: flex; align-items: start; justify-content: space-between; gap: 12px; }
.supplier-review-actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 7px; }
.supplier-review h4 { margin: 0; color: var(--ink); font-size: 13px; font-weight: 800; }
.supplier-review p { margin: 2px 0 0; color: var(--muted); font-size: 11.5px; }
.supplier-suggestion { display: grid; grid-template-columns: minmax(0, 1fr) minmax(240px, 0.6fr); gap: 14px; border-top: 1px solid #edf1f6; padding-top: 10px; }
.supplier-suggestion > div { display: grid; gap: 2px; color: #52657c; font-size: 12px; }
.supplier-suggestion strong { color: var(--ink); }
.supplier-suggestion small { color: var(--muted); }
.supplier-choice { display: grid; align-content: start; gap: 6px; }
.recommended-button { justify-self: end; border: 0; padding: 2px 1px; background: transparent; color: var(--steel); font-size: 11px; font-weight: 750; cursor: pointer; }
.recommended-button:disabled { color: #9aa6b5; cursor: default; }

/* Resumo final: a última coisa lida antes de confirmar a gravação. */
.confirm {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 2px 18px;
  border-radius: 12px;
  background: var(--ink);
  padding: 14px 18px;
  color: #fff;
}
.confirm-kicker { grid-column: 1; color: #a9bbd6; font-family: var(--mono); font-size: 10.5px; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; }
.confirm-target { grid-column: 1; overflow-wrap: anywhere; font-size: 15px; font-weight: 800; }
.confirm dl { display: flex; grid-column: 2; grid-row: 1 / span 2; margin: 0; gap: 22px; }
.confirm dt { color: #a9bbd6; font-size: 10.5px; font-weight: 700; }
.confirm dd { margin: 0; font-family: var(--mono); font-size: 18px; font-weight: 700; font-variant-numeric: tabular-nums; }

@media (max-width: 760px) {
  .supplier-review-header { flex-direction: column; }
  .supplier-suggestion { grid-template-columns: 1fr; }
  .supplier-review-actions { justify-content: flex-start; }
  .confirm { grid-template-columns: 1fr; }
  .confirm dl { grid-column: 1; grid-row: auto; margin-top: 8px; }
}
</style>
