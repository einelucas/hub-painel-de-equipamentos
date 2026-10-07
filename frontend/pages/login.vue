<script setup lang="ts">
definePageMeta({ publicLayout: true });

const { store, login } = useAuth();
const oidcConfigured = Boolean(useRuntimeConfig().public.oidcIssuer);
const email = ref("");
const password = ref("");
const loading = ref(false);
const error = ref("");

if (store.token && await store.loadUser()) await navigateTo("/dashboard");

async function oidc() {
  loading.value = true;
  error.value = "";
  try {
    await login();
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "Não foi possível iniciar o login.";
  } finally {
    loading.value = false;
  }
}

async function submit() {
  loading.value = true;
  error.value = "";
  try {
    await store.loginWithPassword(email.value, password.value);
    await navigateTo("/dashboard");
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "Não foi possível entrar.";
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="login-page">
    <img src="/brand/usina.jpg" alt="" class="login-background" />
    <section class="login-card">
      <img src="/brand/logo-inpasa.png" alt="Inpasa" class="login-logo" />
      <h1>Painel de Equipamentos</h1>
      <p>Acesse com seu e-mail e senha.</p>

      <form class="grid gap-3" @submit.prevent="submit">
        <label class="field">
          <span>E-mail</span>
          <input v-model="email" type="email" autocomplete="username" required autofocus />
        </label>
        <label class="field">
          <span>Senha</span>
          <input v-model="password" type="password" autocomplete="current-password" required />
        </label>
        <button type="submit" class="btn primary login-submit mt-1" :disabled="loading">
          {{ loading ? "Aguarde…" : "Entrar" }}
        </button>
      </form>

      <template v-if="oidcConfigured">
        <div class="my-4 flex items-center gap-3 text-xs text-slate-400">
          <span class="h-px flex-1 bg-slate-200" />ou<span class="h-px flex-1 bg-slate-200" />
        </div>
        <button type="button" class="btn login-submit" :disabled="loading" @click="oidc">
          Entrar com conta corporativa
        </button>
      </template>

      <p v-if="error" class="login-error" role="alert">{{ error }}</p>
    </section>
  </div>
</template>
