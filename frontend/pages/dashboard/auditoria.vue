<script setup lang="ts">
definePageMeta({ middleware: "admin" });
</script>

<template>
  <section>
    <BackLink class="page-back" to="/dashboard">Voltar ao painel</BackLink>
    <ReferenceSectionHeader
      title="Registro de Atividades"
      description="Trilha de eventos administrativos e alterações registradas pelo sistema."
    />
    <AuditViewer />
  </section>
</template>
