<script setup lang="ts">
import { VBtn } from "vuetify/components";
import { Info } from "lucide-vue-next";

/**
 * Lista única de variáveis aceitas pelo backend. Clicar insere no campo
 * ativo do editor; os valores são preenchidos no momento da renderização.
 */
const emit = defineEmits<{ insert: [token: string] }>();

const groups: { name: string; items: { token: string; label: string; hint: string }[] }[] = [
  {
    name: "Equipamento",
    items: [
      { token: "equipamento", label: "Equipamento", hint: "Nome do equipamento" },
      { token: "tag", label: "TAG", hint: "TAG do primeiro componente cadastrado" },
      { token: "unidade", label: "Unidade", hint: "Unidade do contexto do projeto" },
      { token: "obra", label: "Obra", hint: "Nome do contexto do projeto" },
      { token: "responsavel", label: "Responsável", hint: "Responsável cadastrado" },
      { token: "fase", label: "Fase", hint: "Etapa atual do processo (0 a 8)" },
      { token: "status", label: "Status", hint: "Status operacional do equipamento" },
      { token: "criticidade", label: "Criticidade", hint: "Criticidade cadastrada, quando existir" },
    ],
  },
  {
    name: "Prazos e fornecimento",
    items: [
      { token: "fornecedor", label: "Fornecedor", hint: "Fornecedor com vínculo ativo" },
      { token: "prazo_entrega", label: "Prazo de entrega", hint: "Menor prazo de entrega calculado" },
      { token: "dias_restantes", label: "Dias restantes", hint: "Dias até o prazo (negativo se vencido)" },
    ],
  },
  {
    name: "Evento e ação",
    items: [
      { token: "evento", label: "Evento", hint: "Nome do tipo de notificação" },
      { token: "data", label: "Data", hint: "Data do evento ou do startup" },
      { token: "url_equipamento", label: "URL do equipamento", hint: "Link público do equipamento no Hub" },
    ],
  },
];
</script>

<template>
  <section class="tpl-variables">
    <header class="tpl-variables-head">
      <strong>Variáveis dinâmicas</strong>
      <span><Info :size="13" /> Clique para inserir no campo em foco. Valores ausentes são omitidos ou recebem um texto padrão.</span>
    </header>
    <div v-for="group in groups" :key="group.name" class="tpl-variable-group">
      <small>{{ group.name }}</small>
      <div class="tpl-variable-chips">
        <VBtn
          v-for="item in group.items"
          :key="item.token"
          variant="tonal"
          size="x-small"
          type="button"
          :data-testid="`template-variable-${item.token}`"
          :title="item.hint"
          @click="emit('insert', '{' + item.token + '}')"
        >
          {{ item.label }}
        </VBtn>
      </div>
    </div>
  </section>
</template>

<style scoped>
.tpl-variables { display: grid; gap: 10px; border: 1px solid #e2e8f0; border-radius: 10px; padding: 12px; background: #f8fafc; }
.tpl-variables-head { display: grid; gap: 4px; }
.tpl-variables-head strong { font-size: 12px; color: #24364f; }
.tpl-variables-head span { display: flex; gap: 5px; align-items: start; font-size: 11px; color: #64748b; line-height: 1.45; }
.tpl-variable-group { display: grid; gap: 5px; }
.tpl-variable-group small { font-size: 10px; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; color: #7c8ba0; }
.tpl-variable-chips { display: flex; flex-wrap: wrap; gap: 5px; }
</style>
