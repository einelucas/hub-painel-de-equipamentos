<script setup lang="ts">
import { mdiMagnify } from "@mdi/js";
import SkeletonBlock from "~/components/ui/SkeletonBlock.vue";
import { VBtn } from "vuetify/components";
import type { Pagination } from "~/types/equipment";

const props = withDefaults(defineProps<{
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
  showSearch?: boolean;
}>(), { showSearch: true });
const emit = defineEmits<{ reload: []; refresh: []; search: [term: string]; page: [next: number] }>();
const term = ref("");
</script>

<template>
  <div class="stack">
    <div v-if="!props.allowed" class="surface empty-state state-card" role="alert" data-testid="queue-forbidden">
      <h2>Sem permissão</h2>
      <p>Seu perfil não tem acesso à leitura de equipamentos deste módulo.</p>
    </div>
    <template v-else>
      <ModuleFilters
        show-project-context
        :refreshing="props.refreshing || props.loading"
        @change="emit('reload')"
        @refresh="emit('refresh')"
      >
        <form v-if="props.showSearch" class="field field-wide queue-search" @submit.prevent="emit('search', term)">
          <span>Busca</span>
          <div class="search-control">
            <input v-model="term" placeholder="Nome do equipamento">
            <VBtn type="submit" variant="outlined" :prepend-icon="mdiMagnify"> Buscar</VBtn>
          </div>
        </form>
        <slot name="filters" />
        <template v-if="$slots.actions" #actions><slot name="actions" /></template>
      </ModuleFilters>

      <section class="surface">
        <div class="surface-header">
          <div>
            <h2>{{ props.title }}</h2>
            <p>{{ props.description }}</p>
          </div>
          <span v-if="props.refreshing && !props.loading" class="refresh-label" role="status"><span class="spinner-small" aria-hidden="true" /> Atualizando</span>
        </div>
        <p class="queue-criteria">{{ props.criteria }}</p>

        <div v-if="props.loading" class="queue-state" data-testid="queue-loading" role="status" aria-busy="true"><span class="sr-only">Carregando fila...</span><SkeletonBlock :rows="6" /></div>
        <div v-else-if="props.error" class="empty-state table-empty" role="alert" data-testid="queue-error">
          <h2>Não foi possível carregar</h2><p>{{ props.error }}</p>
          <VBtn variant="outlined" @click="emit('reload')">Tentar novamente</VBtn>
        </div>
        <div v-else-if="props.empty" class="empty-state table-empty" data-testid="queue-empty">
          <h2>Nenhum equipamento nesta fila</h2>
          <p>Nada pendente para o recorte selecionado.</p>
        </div>
        <template v-else>
          <div class="table-wrap"><slot /></div>
          <AppPagination
            v-if="props.pagination && props.pagination.totalPages > 1"
            class="pagination"
            :page="props.page"
            :total-pages="props.pagination.totalPages"
            :disabled="props.refreshing"
            @change="emit('page', $event)"
          />
        </template>
      </section>
    </template>
  </div>
</template>

<style scoped>
.state-card { max-width: none; }
.queue-search { min-width: 0; }
.search-control { display: flex; gap: 7px; }
.search-control input { flex: 1; min-width: 0; min-height: 46px; }
.search-control .el-button { flex: none; height: 46px; margin: 0; }
.queue-criteria { margin: 0; padding: 0 18px 12px; color: #8b96a5; font-size: 11.5px; }
.queue-state { display: block; padding: 18px; min-height: 220px; align-items: center; justify-content: center; gap: 12px; color: #748197; }
.table-wrap { padding: 0 18px 18px; overflow-x: auto; }
.table-empty { margin: auto; padding-bottom: 28px; }
.refresh-label { display: inline-flex; align-items: center; gap: 7px; color: #748197; font-size: 12px; }
.spinner-small { width: 16px; height: 16px; border-width: 2px; }
.pagination { display: flex; align-items: center; justify-content: flex-end; gap: 12px; padding: 0 18px 18px; color: #68778c; font-size: 12px; }
</style>
