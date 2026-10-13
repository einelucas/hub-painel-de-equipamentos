<script setup lang="ts">
definePageMeta({ publicLayout: true });

const { store, login } = useAuth();
const oidcConfigured = Boolean(useRuntimeConfig().public.oidcIssuer);
const email = ref("");
const password = ref("");
const loading = ref(false);
const error = ref("");

const checking = ref(Boolean(store.token));
try {
  if (store.token && await store.loadUser()) await navigateTo("/dashboard");
} finally {
  checking.value = false;
}

async function oidc() {
  if (loading.value) return;
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
  if (loading.value) return;
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

      <p v-if="checking" class="login-checking" role="status"><span class="spinner-small" aria-hidden="true" /> Verificando sessão...</p>
      <form class="grid gap-3" :aria-busy="loading" @submit.prevent="submit">
        <label class="field">
          <span>E-mail</span>
          <input v-model="email" type="email" autocomplete="username" required autofocus />
        </label>
        <label class="field">
          <span>Senha</span>
          <input v-model="password" type="password" autocomplete="current-password" required />
        </label>
        <button type="submit" class="btn primary login-submit mt-1" :disabled="loading || checking" :aria-busy="loading">
          <span v-if="loading" class="spinner-small" aria-hidden="true" />
          {{ loading ? "Entrando..." : "Entrar" }}
        </button>
      </form>

      <template v-if="oidcConfigured">
        <div class="my-4 flex items-center gap-3 text-xs text-slate-400">
          <span class="h-px flex-1 bg-slate-200" />ou<span class="h-px flex-1 bg-slate-200" />
        </div>
        <button type="button" class="btn login-submit" :disabled="loading || checking" @click="oidc">
          Entrar com conta corporativa
        </button>
      </template>

      <p v-if="error" class="login-error" role="alert">{{ error }}</p>
    </section>
  </div>
</template>

<style scoped>
.login-checking { display: flex; align-items: center; gap: 8px; margin: 0 0 8px; color: #748197; font-size: 12.5px; }
</style>
