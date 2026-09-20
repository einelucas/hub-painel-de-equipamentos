<script setup lang="ts">
import { Search } from "lucide-vue-next";
import type { Pagination } from "~/types/equipment";

const props = defineProps<{
  title: string;
  description: string;
  criteria: string;
  loading: boolean;
  refreshing: boolean;
  error: string;
  empty: boolean;
  pagination: Pagination | null;
  page: number;
  allowed: boolean;
}>();
const emit = defineEmits<{ reload: []; search: [term: string]; page: [next: number] }>();
const term = ref("");
</script>

<template>
  <div class="stack">
    <div v-if="!props.allowed" class="surface empty-state state-card" role="alert" data-testid="queue-forbidden">
      <h2>Sem permissão</h2>
      <p>Seu perfil não tem acesso à leitura de equipamentos deste módulo.</p>
    </div>
    <template v-else>
      <ModuleFilters :refreshing="props.refreshing" @change="emit('reload')">
        <form class="field queue-search" @submit.prevent="emit('search', term)">
          <span>Busca</span>
          <div class="search-control">
            <input v-model="term" placeholder="Nome do equipamento">
            <button class="btn" type="submit"><Search :size="16" /> Buscar</button>
          </div>
        </form>
        <template #actions><slot name="actions" /></template>
      </ModuleFilters>

      <section class="surface">
        <div class="surface-header">
          <div>
            <h2>{{ props.title }}</h2>
            <p>{{ props.description }}</p>
          </div>
          <span v-if="props.refreshing && !props.loading" class="refresh-label"><span class="spinner spinner-small" /> Atualizando</span>
        </div>
        <p class="queue-criteria">{{ props.criteria }}</p>

        <div v-if="props.loading" class="queue-state" data-testid="queue-loading"><span class="spinner" /> Carregando fila...</div>
        <div v-else-if="props.error" class="empty-state table-empty" role="alert" data-testid="queue-error">
          <h2>Não foi possível carregar</h2><p>{{ props.error }}</p>
          <button class="btn" @click="emit('reload')">Tentar novamente</button>
        </div>
        <div v-else-if="props.empty" class="empty-state table-empty" data-testid="queue-empty">
          <h2>Nenhum equipamento nesta fila</h2>
          <p>Nada pendente para o recorte selecionado.</p>
        </div>
        <template v-else>
          <div class="table-wrap"><slot /></div>
          <div v-if="props.pagination && props.pagination.totalPages > 1" class="pagination">
            <button class="btn small" :disabled="props.page <= 1" @click="emit('page', props.page - 1)">Anterior</button>
            <span>Página {{ props.page }} de {{ props.pagination.totalPages }}</span>
            <button class="btn small" :disabled="props.page >= props.pagination.totalPages" @click="emit('page', props.page + 1)">Próxima</button>
          </div>
        </template>
      </section>
    </template>
  </div>
</template>

<style scoped>
.state-card { max-width: none; }
.queue-search { min-width: 0; }
.search-control { display: flex; gap: 7px; }
.queue-criteria { margin: 0; padding: 0 18px 12px; color: #8b96a5; font-size: 11.5px; }
.queue-state { display: flex; min-height: 220px; align-items: center; justify-content: center; gap: 12px; color: #748197; }
.table-wrap { padding: 0 18px 18px; overflow-x: auto; }
.table-empty { margin: auto; padding-bottom: 28px; }
.refresh-label { display: inline-flex; align-items: center; gap: 7px; color: #748197; font-size: 12px; }
.spinner-small { width: 16px; height: 16px; border-width: 2px; }
.pagination { display: flex; align-items: center; justify-content: flex-end; gap: 12px; padding: 0 18px 18px; color: #68778c; font-size: 12px; }
</style>
