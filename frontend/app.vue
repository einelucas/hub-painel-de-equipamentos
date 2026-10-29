<template>
  <VApp class="hub-app">
    <NuxtLoadingIndicator color="#304f7e" :height="3" />
    <NuxtLayout>
      <NuxtPage />
    </NuxtLayout>
    <ConfirmDialog />
  </VApp>
</template>

<style>
.hub-app { font-family: "Manrope", system-ui, sans-serif; }
</style>
