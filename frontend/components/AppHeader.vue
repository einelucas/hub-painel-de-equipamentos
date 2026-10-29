<script setup lang="ts">
import { mdiArrowLeft, mdiBellOutline, mdiCloudDownloadOutline } from "@mdi/js";
import { VBtn } from "vuetify/components";
import { History, Search } from "lucide-vue-next";

const router = useRouter();
const { store } = useAuth();
</script>

<template>
  <header class="flex h-16 items-center gap-4 border-b border-black/[0.07] bg-background px-4 sm:px-6">
    <div class="flex shrink-0 items-center gap-3">
      <NuxtLink to="/dashboard" aria-label="Painel de Equipamentos">
        <img src="/brand/hub-logo.png" alt="Hub" class="h-9 w-auto" />
      </NuxtLink>

      <VBtn
        type="button"
        variant="outlined"
        :prepend-icon="mdiArrowLeft"
        @click="router.back()"
      >
        Voltar
      </VBtn>

      <div class="hidden sm:block">
        <p class="text-[9.92px] font-extrabold uppercase leading-none tracking-[0.08em] text-[#8a97ab]">
          Planejamento
        </p>
        <p class="mt-1 text-[16px] font-extrabold leading-none tracking-tight text-[#20324a]">
          Painel de Equipamentos
        </p>
      </div>
    </div>

    <label class="relative mx-auto hidden w-[480px] max-w-full shrink items-center sm:flex">
      <Search class="pointer-events-none absolute left-3.5 size-4 text-muted-foreground" />
      <input
        type="search"
        placeholder="Buscar"
        aria-label="Buscar no módulo"
        class="h-10 w-full rounded-full bg-white pl-10 pr-4 text-[15px] text-foreground shadow-[0_2px_4px_rgba(15,23,42,0.12)] outline-none placeholder:text-muted-foreground focus:ring-2 focus:ring-ring/40"
      />
    </label>

    <div class="flex shrink-0 items-center gap-1.5">
      <VBtn
        type="button"
        variant="text"
        size="small"
        aria-label="Notificações"
        title="Notificações do Hub"
        :icon="mdiBellOutline"
      />

      <NuxtLink
        v-if="store.user?.role === 'ADMIN'"
        to="/dashboard/auditoria"
        class="flex h-[34px] items-center gap-1.5 rounded-[4px] bg-primary/10 px-3.5 text-[13px] font-medium text-primary transition-colors hover:bg-primary/15"
      >
        <History class="size-[15px]" />
        Registro de Atividades
      </NuxtLink>

      <VBtn
        type="button"
        variant="text"
        size="small"
        aria-label="Exportar dados"
        title="Exportação disponível quando houver dados no módulo"
        :icon="mdiCloudDownloadOutline"
      />

      <UserMenu />
    </div>
  </header>
</template>
