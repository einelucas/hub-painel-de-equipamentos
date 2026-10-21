<script setup lang="ts">
definePageMeta({ middleware: "admin" });
</script>

<template>
  <section class="stack">
    <BackLink class="page-back" to="/equipamentos">Voltar aos equipamentos</BackLink>
    <ReferenceSectionHeader
      title="Configuração de e-mails"
      description="Regras, caixa de testes e histórico de notificações do Painel de Equipamentos."
    />
    <div class="surface" style="padding: 20px">
      <NotificationCenter />
    </div>
  </section>
</template>
