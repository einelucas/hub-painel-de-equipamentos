<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { ArrowRight, Building2, History } from "lucide-vue-next";
import Button from "~/components/ui/Button.vue";
import SupplierCombobox from "~/components/imports/SupplierCombobox.vue";
import type { EquipmentSupplier, Supplier } from "~/types/equipment";
import { formatDateTime } from "~/utils/format";
import { formatCnpj } from "~/utils/suppliers";

export interface SupplierLinkValues {
  supplierId: string;
  role: string | null;
  changeReason: string | null;
}

/**
 * Vincular ou substituir o fornecedor de um equipamento (no máximo um ativo).
 * Na substituição, mostra a troca "sai → entra" antes de confirmar; o vínculo
 * anterior é encerrado e vai para o histórico.
 */
const props = defineProps<{
  open: boolean;
  /** Vínculo ativo; `null` = primeiro vínculo. */
  current: EquipmentSupplier | null;
  suppliers: Supplier[];
  busy: boolean;
  error: string;
}>();
const emit = defineEmits<{ close: []; submit: [values: SupplierLinkValues] }>();

const REASON_LIMIT = 500;
const chosen = ref("");
const role = ref("");
const reason = ref("");

const replacing = computed(() => props.current !== null);
const selected = computed(() => props.suppliers.find((item) => item.id === chosen.value) ?? null);

// Cada abertura começa limpa.
watch(
  () => props.open,
  (isOpen) => {
    if (!isOpen) return;
    chosen.value = "";
    role.value = "";
    reason.value = "";
  },
  { immediate: true },
);

function submit(): void {
  if (!chosen.value) return;
  emit("submit", {
    supplierId: chosen.value,
    role: role.value.trim() || null,
    changeReason: reason.value.trim() || null,
  });
}

function cnpj(supplier: Pick<Supplier, "taxId">): string | null {
  return supplier.taxId ? formatCnpj(supplier.taxId) : null;
}
</script>

<template>
  <AppModal :open="props.open" :title="replacing ? 'Substituir fornecedor' : 'Vincular fornecedor'" @close="emit('close')">
    <form class="link-form" @submit.prevent="submit">
      <!-- A troca, lado a lado: o que sai e o que entra. -->
      <div class="swap" :class="{ 'swap--single': !replacing }">
        <article v-if="props.current" class="party party--out" data-testid="supplier-swap-out">
          <span class="party-tag">Sai</span>
          <strong>{{ props.current.supplier.legalName }}</strong>
          <small v-if="cnpj(props.current.supplier)" class="mono">{{ cnpj(props.current.supplier) }}</small>
          <small>Desde {{ formatDateTime(props.current.startedAt) }}<template v-if="props.current.role"> · {{ props.current.role }}</template></small>
        </article>
        <ArrowRight v-if="replacing" class="swap-arrow" :size="18" aria-hidden="true" />
        <article class="party party--in" :class="{ 'party--empty': !selected }" data-testid="supplier-swap-in">
          <span class="party-tag">Entra</span>
          <template v-if="selected">
            <strong>{{ selected.legalName }}</strong>
            <small v-if="selected.tradeName">{{ selected.tradeName }}</small>
            <small class="mono">
              <template v-if="selected.corporateCode">{{ selected.corporateCode }} · </template>{{ cnpj(selected) ?? "sem CNPJ" }}
            </small>
          </template>
          <template v-else>
            <Building2 :size="18" aria-hidden="true" />
            <small>Escolha o fornecedor abaixo</small>
          </template>
        </article>
      </div>

      <div class="field">
        <span>Fornecedor *</span>
        <SupplierCombobox
          v-model="chosen"
          :suppliers="props.suppliers"
          label="Fornecedor"
          empty-label="Selecione"
          empty-value=""
          test-id="supplier-link-combobox"
        />
      </div>
      <p v-if="props.suppliers.length === 0" class="link-hint">
        Nenhum fornecedor disponível. Cadastre um em
        <NuxtLink to="/fornecedores">Fornecedores</NuxtLink>.
      </p>

      <div class="link-grid">
        <label class="field">
          <span>Papel <em>opcional</em></span>
          <input v-model="role" maxlength="80" placeholder="Ex.: Fabricante">
        </label>
        <label class="field reason-field">
          <span>
            {{ replacing ? "Motivo da substituição" : "Observação" }} <em>opcional</em>
            <small class="counter mono" aria-hidden="true">{{ reason.length }}/{{ REASON_LIMIT }}</small>
          </span>
          <textarea
            v-model="reason"
            :maxlength="REASON_LIMIT"
            rows="3"
            :placeholder="replacing ? 'Ex.: fornecedor anterior não atende ao prazo' : 'Registrado no histórico do vínculo'"
          />
        </label>
      </div>

      <p v-if="props.error" class="notice error" role="alert">{{ props.error }}</p>

      <footer class="link-footer">
        <p v-if="replacing" class="link-note">
          <History :size="13" aria-hidden="true" /> O vínculo atual é encerrado e fica no histórico.
        </p>
        <div class="form-actions">
          <Button variant="outline" @click="emit('close')">Cancelar</Button>
          <Button
            type="submit"
            variant="default"
            :loading="props.busy"
            :disabled="!chosen"
          >
            {{ props.busy ? "Salvando..." : replacing ? "Substituir" : "Vincular" }}
          </Button>
        </div>
      </footer>
    </form>
  </AppModal>
</template>

<style scoped>
.link-form {
  --ink: #1f3352;
  --steel: #304f7e;
  --wash: #f3f6fb;
  --rule: #dde5ef;
  --muted: #6b7a8f;
  --mono: ui-monospace, "Cascadia Mono", "SFMono-Regular", Consolas, monospace;

  display: grid;
  gap: 16px;
}
.mono { font-family: var(--mono); font-variant-numeric: tabular-nums; }

/* ---------- Sai → Entra ---------- */
.swap { display: grid; grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr); align-items: stretch; gap: 10px; }
.swap--single { grid-template-columns: minmax(0, 1fr); }
.swap-arrow { align-self: center; color: var(--steel); }
.party { display: grid; align-content: start; gap: 3px; min-width: 0; border-radius: 12px; padding: 12px 14px; }
.party strong { overflow: hidden; font-size: 13px; font-weight: 800; text-overflow: ellipsis; }
.party small { color: var(--muted); font-size: 11px; overflow-wrap: anywhere; }
.party-tag { justify-self: start; margin-bottom: 4px; border-radius: 5px; padding: 1px 6px; font-family: var(--mono); font-size: 10px; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; }
.party--out { border: 1px solid var(--rule); background: var(--wash); color: #8592a6; }
.party--out strong { color: #6b7a8f; text-decoration: line-through; text-decoration-color: rgb(107 122 143 / 45%); }
.party--out .party-tag { background: #e4e9f0; color: var(--muted); }
.party--in { border: 1.5px solid var(--steel); background: #fff; color: var(--ink); box-shadow: 0 6px 18px rgb(48 79 126 / 10%); }
.party--in .party-tag { background: var(--steel); color: #fff; }
.party--empty { place-items: start; border-style: dashed; border-color: #b9c8db; box-shadow: none; color: #a3b1c4; }
.party--empty .party-tag { background: #e4e9f0; color: var(--muted); }

/* ---------- Campos ---------- */
.link-grid { display: grid; grid-template-columns: minmax(0, 0.8fr) minmax(0, 1.2fr); gap: 12px; }
.field > span em { margin-left: 4px; color: #a3adbb; font-style: normal; font-weight: 600; letter-spacing: 0; text-transform: none; }
.reason-field > span { display: flex; align-items: baseline; }
.counter { margin-left: auto; color: #a3adbb; font-size: 10.5px; font-weight: 600; letter-spacing: 0; text-transform: none; }
.reason-field textarea { min-height: 84px; resize: vertical; }
.link-hint { margin: -8px 0 0; color: var(--muted); font-size: 11.5px; }

/* ---------- Rodapé ---------- */
.link-footer { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 10px; border-top: 1px solid var(--rule); padding-top: 14px; }
.link-note { display: inline-flex; align-items: center; gap: 6px; margin: 0; color: var(--muted); font-size: 11.5px; }
.form-actions { display: flex; gap: 9px; margin-left: auto; }

@media (max-width: 620px) {
  .swap { grid-template-columns: 1fr; }
  .swap-arrow { justify-self: center; transform: rotate(90deg); }
  .link-grid { grid-template-columns: 1fr; }
}
</style>
