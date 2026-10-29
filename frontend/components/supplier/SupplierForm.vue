<script setup lang="ts">
import { computed, reactive, useId, watch } from "vue";
import { AlertTriangle, CheckCircle2 } from "lucide-vue-next";
import { mdiCheck, mdiClose } from "@mdi/js";
import { VBtn } from "vuetify/components";
import type { Supplier } from "~/types/equipment";
import { cnpjStatus, formatCnpj, maskCnpjInput, normalizeCnpj, supplierLabel } from "~/utils/suppliers";

export interface SupplierFormValues {
  corporateCode: string | null;
  legalName: string;
  tradeName: string | null;
  taxId: string | null;
  /** Só na edição: ativar/desativar o cadastro. */
  active?: boolean;
}

/**
 * Formulário único de fornecedor (página Fornecedores e painel de Suprimentos).
 * Mostra, enquanto se digita, como o fornecedor vai aparecer nos seletores do Hub.
 */
const props = withDefaults(
  defineProps<{
    /** `null` = novo fornecedor. */
    supplier: Supplier | null;
    saving: boolean;
    error?: string;
    /** `compact`: dentro de painéis (sem prévia), ocupando menos altura. */
    compact?: boolean;
  }>(),
  { error: "", compact: false },
);
const emit = defineEmits<{ submit: [values: SupplierFormValues]; cancel: [] }>();

const form = reactive({ corporateCode: "", legalName: "", tradeName: "", taxId: "", active: true });
const localError = reactive({ message: "" });
const statusId = `cnpj-status-${useId()}`;

watch(
  () => props.supplier,
  (supplier) => {
    Object.assign(form, {
      corporateCode: supplier?.corporateCode ?? "",
      legalName: supplier?.legalName ?? "",
      tradeName: supplier?.tradeName ?? "",
      taxId: supplier?.taxId ? formatCnpj(supplier.taxId) : "",
      active: supplier?.active ?? true,
    });
    localError.message = "";
  },
  { immediate: true },
);

const editing = computed(() => props.supplier !== null);
const status = computed(() => cnpjStatus(form.taxId));
const STATUS_TEXT: Record<ReturnType<typeof cnpjStatus>, string> = {
  empty: "Opcional",
  incomplete: "Incompleto: o CNPJ tem 14 dígitos",
  valid: "CNPJ válido",
  invalid: "Dígitos verificadores não conferem",
  other: "Documento fora do padrão CNPJ",
};

/** Mesmo rótulo usado nos seletores de fornecedor. */
const preview = computed(() =>
  supplierLabel({
    corporateCode: form.corporateCode.trim() || null,
    legalName: form.legalName.trim() || "Razão social",
  }),
);

function onTaxIdInput(event: Event): void {
  form.taxId = maskCnpjInput((event.target as HTMLInputElement).value);
}

function submit(): void {
  if (!form.legalName.trim()) {
    localError.message = "Informe a razão social.";
    return;
  }
  localError.message = "";
  const values: SupplierFormValues = {
    corporateCode: form.corporateCode.trim() || null,
    legalName: form.legalName.trim(),
    tradeName: form.tradeName.trim() || null,
    // Grava só os dígitos, como o restante da base.
    taxId: normalizeCnpj(form.taxId),
  };
  if (editing.value) values.active = form.active;
  emit("submit", values);
}
</script>

<template>
  <form class="supplier-form" :class="{ 'supplier-form--compact': props.compact }" @submit.prevent="submit">
    <div v-if="!props.compact" class="preview" aria-live="polite" data-testid="supplier-preview">
      <span class="preview-tag">Nos seletores</span>
      <strong :class="{ placeholder: !form.legalName.trim() }">{{ preview }}</strong>
      <small>
        <template v-if="form.tradeName.trim()">{{ form.tradeName.trim() }} · </template>
        <span class="mono">{{ status === "empty" ? "sem CNPJ" : form.taxId }}</span>
      </small>
    </div>
    <p v-else class="compact-title">{{ editing ? `Editar ${props.supplier?.legalName}` : "Novo fornecedor" }}</p>

    <div class="row row--ids">
      <label class="field">
        <span>Código <em>opcional</em></span>
        <input v-model="form.corporateCode" class="mono" maxlength="20" placeholder="Ex.: 9001" data-testid="supplier-code">
      </label>
      <label class="field">
        <span>CNPJ</span>
        <input
          :value="form.taxId"
          class="mono"
          inputmode="numeric"
          maxlength="18"
          placeholder="00.000.000/0000-00"
          :aria-describedby="statusId"
          @input="onTaxIdInput"
        >
        <small :id="statusId" class="cnpj-status" :class="`cnpj-status--${status}`" data-testid="cnpj-status">
          <CheckCircle2 v-if="status === 'valid'" :size="12" aria-hidden="true" />
          <AlertTriangle v-else-if="status === 'invalid' || status === 'other'" :size="12" aria-hidden="true" />
          {{ STATUS_TEXT[status] }}
        </small>
      </label>
    </div>

    <label class="field">
      <span>Razão social *</span>
      <input v-model="form.legalName" maxlength="200" required placeholder="Como consta no CNPJ">
    </label>
    <label class="field">
      <span>Nome fantasia <em>opcional</em></span>
      <input v-model="form.tradeName" maxlength="200">
    </label>

    <label v-if="editing" class="active-tile" :class="{ on: form.active }">
      <input v-model="form.active" type="checkbox">
      <span>
        <strong>{{ form.active ? "Fornecedor ativo" : "Fornecedor inativo" }}</strong>
        <small>Fornecedores não são excluídos: desative para tirá-los de uso nos vínculos.</small>
      </span>
    </label>

    <p v-if="localError.message || props.error" class="form-error" role="alert">{{ localError.message || props.error }}</p>

    <div class="form-actions">
      <VBtn
        variant="outlined"
        :size="props.compact ? 'small' : undefined"
        :prepend-icon="props.compact ? mdiClose : undefined"
        @click="emit('cancel')"
      >
        Cancelar
      </VBtn>
      <VBtn
        type="submit"
        variant="tonal"
        :size="props.compact ? 'small' : undefined"
        :prepend-icon="props.compact && !props.saving ? mdiCheck : undefined"
        :loading="props.saving"
        :disabled="props.saving"
      >
        {{ props.saving ? "Salvando..." : editing ? "Salvar alterações" : "Cadastrar fornecedor" }}
      </VBtn>
    </div>
  </form>
</template>

<style scoped>
.supplier-form {
  --ink: #1f3352;
  --steel: #304f7e;
  --wash: #f3f6fb;
  --rule: #dde5ef;
  --muted: #6b7a8f;
  --go: #3f7a2e;
  --caution: #8a5a12;
  --mono: ui-monospace, "Cascadia Mono", "SFMono-Regular", Consolas, monospace;

  display: grid;
  gap: 14px;
}
.supplier-form--compact { gap: 10px 12px; border: 1px solid #c9d8ec; border-radius: 12px; padding: 14px; background: var(--wash); }
.mono { font-family: var(--mono); font-variant-numeric: tabular-nums; }
.field > span em { margin-left: 4px; color: #a3adbb; font-style: normal; font-weight: 600; letter-spacing: 0; text-transform: none; }

/* Prévia: exatamente o rótulo que os seletores do Hub vão mostrar. */
.preview { display: grid; gap: 2px; border-radius: 12px; padding: 12px 14px; background: var(--ink); color: #fff; }
.preview-tag { color: #a9bbd6; font-family: var(--mono); font-size: 10px; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; }
.preview strong { overflow: hidden; font-size: 14px; font-weight: 800; text-overflow: ellipsis; white-space: nowrap; }
.preview strong.placeholder { color: #8195b3; font-weight: 700; }
.preview small { overflow: hidden; color: #c4d2e6; font-size: 11.5px; text-overflow: ellipsis; white-space: nowrap; }
.compact-title { margin: 0; overflow: hidden; color: var(--ink); font-size: 12.5px; font-weight: 800; text-overflow: ellipsis; white-space: nowrap; }

.row--ids { display: grid; grid-template-columns: minmax(0, 0.7fr) minmax(0, 1.3fr); gap: 12px; align-items: start; }
.cnpj-status { display: inline-flex; align-items: center; gap: 4px; margin-top: 2px; color: var(--muted); font-size: 11px; font-weight: 700; }
.cnpj-status--valid { color: var(--go); }
.cnpj-status--invalid, .cnpj-status--other { color: var(--caution); }
.cnpj-status--empty { font-weight: 600; }

.active-tile { display: flex; align-items: flex-start; gap: 10px; border: 1px solid var(--rule); border-radius: 10px; padding: 11px 12px; background: #fff; cursor: pointer; }
.active-tile.on { border-color: #b8d3ad; background: #f6fbf3; }
.active-tile input { width: 16px; height: 16px; margin-top: 1px; accent-color: var(--go); }
.active-tile span { display: grid; gap: 2px; }
.active-tile strong { color: var(--ink); font-size: 12.5px; }
.active-tile small { color: var(--muted); font-size: 11.5px; }
.active-tile:focus-within { outline: 2px solid var(--steel); outline-offset: 2px; }

.form-error { margin: 0; color: #a4453a; font-size: 12px; font-weight: 700; }
.form-actions { display: flex; justify-content: flex-end; gap: 9px; border-top: 1px solid var(--rule); padding-top: 14px; }
.supplier-form--compact .form-actions { border-top: 0; padding-top: 0; }
@media (max-width: 560px) { .row--ids { grid-template-columns: 1fr; } }
</style>
