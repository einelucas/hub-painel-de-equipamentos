<script setup lang="ts">
definePageMeta({ publicLayout: true });
const { completeLogin } = useAuth();
const error = ref("");
let started = false;

onMounted(async () => {
  if (started) return;
  started = true;
  try {
    await completeLogin();
    await navigateTo("/dashboard");
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "Falha ao concluir autenticação.";
  }
});
</script>

<template>
  <div class="grid min-h-screen place-items-center bg-slate-100">
    <div class="text-center">
      <div v-if="!error" class="spinner mx-auto" aria-hidden="true" />
      <h1 class="mt-4 text-xl font-extrabold text-brand-dark" :role="error ? undefined : 'status'">{{ error ? "Concluindo autenticação" : "Entrando..." }}</h1>
      <p v-if="!error" class="mt-1 text-sm text-slate-500">Concluindo autenticação, aguarde.</p>
      <VAlert v-if="error" class="mt-3" type="error" role="alert">{{ error }}</VAlert>
      <BackLink v-if="error" class="mt-4" to="/login">Voltar ao login</BackLink>
    </div>
  </div>
</template>
