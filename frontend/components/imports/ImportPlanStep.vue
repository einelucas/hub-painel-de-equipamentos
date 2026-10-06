<script setup lang="ts">
import { computed } from "vue";
import ImportCatalogSummary from "~/components/imports/ImportCatalogSummary.vue";
import { useImportState } from "~/composables/useImportState";

/**
 * Passo 4: plano do motor + confirmação explícita. Com item BLOCKED (ou mapping
 * inválido) o botão de confirmar fica desabilitado; nada é aplicado automaticamente.
 */
const { plan, batches, totals: sourceTotals, selectedContext, busy, stale, apply, step } = useImportState();

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
</script>

<template>
  <div class="import-step" data-testid="import-step-plan">
    <p v-if="stale" class="import-stale" role="alert" data-testid="import-stale">
      Os dados mudaram desde que o plano foi gerado. Gere o plano novamente antes de aplicar.
    </p>

    <template v-if="plan">
      <table class="plan-table">
        <thead><tr><th>Grupo</th><th>Criar</th><th>Atualizar</th><th>Sem alteração</th><th>Bloqueados</th></tr></thead>
        <tbody>
          <tr v-for="group in plan.groups" :key="group.name" :data-testid="`plan-group-${group.name}`">
            <td>{{ group.name }}</td><td>{{ group.create }}</td><td>{{ group.update }}</td><td>{{ group.noop }}</td>
            <td :class="{ 'plan-blocked': group.blocked > 0 }">{{ group.blocked }}</td>
          </tr>
        </tbody>
      </table>

      <section v-if="plan.mappingIssues.length" class="plan-list plan-list--error" data-testid="plan-mapping-issues">
        <h4>Mapeamento inválido</h4>
        <ul><li v-for="(issue, index) in plan.mappingIssues" :key="index">{{ issue.message }}</li></ul>
      </section>
      <section v-if="plan.blocked.length" class="plan-list plan-list--error" data-testid="plan-blocked">
        <h4>Itens bloqueados ({{ plan.blocked.length }})</h4>
        <ul>
          <li v-for="item in plan.blocked" :key="`${item.group}-${item.sourceKey}`">
            <strong>{{ item.group }} · {{ item.label }}</strong>
            <span v-for="issue in item.issues" :key="issue.code" class="issue-meta">{{ issue.message }}</span>
          </li>
        </ul>
      </section>
      <section class="plan-list plan-list--info" data-testid="plan-eap">
        <h4>EAP dos equipamentos</h4>
        <ul>
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

      <section v-if="equipmentWarnings.length" class="plan-list plan-list--warning" data-testid="plan-equipment-warnings">
        <h4>Pendências que não bloqueiam ({{ equipmentWarnings.length }} equipamentos)</h4>
        <ul>
          <li v-for="item in equipmentWarnings" :key="item.sourceKey">
            <strong>{{ item.label }}</strong>
            <span v-for="issue in item.issues" :key="issue.code" class="issue-meta">{{ issue.message }}</span>
          </li>
        </ul>
      </section>
      <section v-if="plan.warnings.length" class="plan-list plan-list--warning">
        <h4>Avisos ({{ plan.warnings.length }})</h4>
        <ul><li v-for="(warning, index) in plan.warnings" :key="index">{{ warning.message }}</li></ul>
      </section>

      <section class="confirm" data-testid="import-confirm-summary" aria-label="Resumo da importação">
        <h4>Confirmação</h4>
        <dl>
          <div><dt>Obra</dt><dd>{{ selectedContext ? `${selectedContext.code} · ${selectedContext.name}` : "—" }}</dd></div>
          <div><dt>Arquivos</dt><dd data-testid="confirm-files">{{ batches.length }}</dd></div>
          <div><dt>Equipamentos</dt><dd>{{ sourceTotals.equipments }}</dd></div>
          <div><dt>Componentes</dt><dd>{{ sourceTotals.components }}</dd></div>
          <div><dt>Criar</dt><dd>{{ totals.create }}</dd></div>
          <div><dt>Atualizar</dt><dd>{{ totals.update }}</dd></div>
          <div><dt>Sem alteração</dt><dd>{{ totals.noop }}</dd></div>
          <div><dt>Bloqueados</dt><dd data-testid="confirm-blocked">{{ totals.blocked }}</dd></div>
          <div><dt>Catálogos a criar</dt><dd data-testid="confirm-catalog-creates">{{ catalogCreates }}</dd></div>
        </dl>
      </section>
    </template>

    <div class="import-actions">
      <button type="button" class="btn" :disabled="busy" @click="step = 'mapping'">Voltar ao mapeamento</button>
      <button
        type="button"
        class="btn primary"
        :disabled="!plan?.canApply || busy"
        data-testid="import-confirm"
        @click="apply"
      >
        {{ busy ? "Importando..." : "Confirmar importação" }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.import-step { display: grid; gap: 12px; }
.import-stale { margin: 0; border-radius: 9px; background: #fdf6e7; padding: 8px 11px; color: #8a5a12; font-size: 12px; font-weight: 700; }
.plan-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.plan-table th { color: #7a879a; font-size: 11px; font-weight: 750; text-align: left; }
.plan-table th, .plan-table td { border-bottom: 1px solid #f0f3f7; padding: 5px 6px; }
.plan-table td:first-child { color: #2b3e58; font-weight: 700; }
.plan-blocked { color: #a4453a; font-weight: 800; }
.plan-list { border-radius: 10px; padding: 9px 12px; }
.plan-list--error { background: #fbeeed; }
.plan-list--warning { background: #fdf6e7; }
.plan-list--info { background: #f2f6fb; }
.plan-list h4, .confirm h4 { margin: 0 0 6px; color: #2b3e58; font-size: 12px; font-weight: 800; }
.plan-list ul { display: grid; margin: 0; padding: 0; gap: 5px; list-style: none; max-height: 150px; overflow-y: auto; font-size: 12px; color: #2b3e58; }
.plan-list li { display: grid; gap: 1px; }
.issue-meta { color: #7a879a; font-size: 11px; }
.confirm { border: 1px solid #e4e9f0; border-radius: 10px; padding: 10px 12px; background: #f8fafc; }
.confirm dl { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); margin: 0; gap: 6px 12px; }
.confirm dt { color: #7a879a; font-size: 11px; }
.confirm dd { margin: 0; color: #2b3e58; font-size: 12.5px; font-weight: 750; overflow-wrap: anywhere; }
.import-actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 8px; }
@media (max-width: 620px) { .confirm dl { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
</style>
