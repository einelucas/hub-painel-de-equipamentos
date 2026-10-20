<script setup lang="ts">
definePageMeta({ middleware: "admin" });
</script>

<template>
  <section class="stack">
    <NuxtLink class="admin-back" to="/equipamentos">← Voltar aos equipamentos</NuxtLink>
    <ReferenceSectionHeader
      title="Configuração de e-mails"
      description="Regras, caixa de testes e histórico de notificações do Painel de Equipamentos."
    />
    <div class="surface" style="padding: 20px">
      <NotificationCenter />
    </div>
  </section>
</template>
