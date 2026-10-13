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
      <p v-if="error" class="notice error mt-3">{{ error }}</p>
      <NuxtLink v-if="error" class="btn mt-3" to="/login">Voltar ao login</NuxtLink>
    </div>
  </div>
</template>
