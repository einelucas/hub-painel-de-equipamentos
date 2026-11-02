<script setup lang="ts">
import { VBtn } from "vuetify/components";

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

const changeOpen = ref(false);
const newPassword = ref("");
const confirmPassword = ref("");
const changeError = ref("");
const DEFAULT_PASSWORD = "INP@2026";

function passwordProblem(): string {
  if (newPassword.value.length < 8) return "A nova senha deve ter ao menos 8 caracteres.";
  if (!/[A-Za-z]/.test(newPassword.value) || !/\d/.test(newPassword.value)) return "A nova senha deve conter letras e números.";
  if (newPassword.value === DEFAULT_PASSWORD) return "A nova senha não pode ser a senha padrão.";
  if (newPassword.value !== confirmPassword.value) return "A confirmação não confere com a nova senha.";
  return "";
}

function closeChange() {
  if (loading.value) return;
  changeOpen.value = false;
  newPassword.value = "";
  confirmPassword.value = "";
  changeError.value = "";
}

async function submitNewPassword() {
  if (loading.value) return;
  changeError.value = passwordProblem();
  if (changeError.value) return;
  loading.value = true;
  try {
    await store.setInitialPassword(email.value, password.value, newPassword.value);
    changeOpen.value = false;
    await navigateTo("/dashboard");
  } catch (cause) {
    changeError.value = cause instanceof Error ? cause.message : "Não foi possível definir a nova senha.";
  } finally {
    loading.value = false;
  }
}

async function submit() {
  if (loading.value) return;
  loading.value = true;
  error.value = "";
  try {
    if ((await store.loginWithPassword(email.value, password.value)) === "password-change-required") {
      changeOpen.value = true;
      return;
    }
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
        <div class="field">
          <VTextField v-model="email" label="E-mail" type="email" autocomplete="username" required autofocus />
        </div>
        <div class="field">
          <VTextField v-model="password" label="Senha" type="password" autocomplete="current-password" required />
        </div>
        <VBtn type="submit" variant="flat" color="primary" class="mt-1" block :disabled="checking" :loading="loading">
          {{ loading ? "Entrando..." : "Entrar" }}
        </VBtn>
      </form>

      <template v-if="oidcConfigured">
        <div class="my-4 flex items-center gap-3 text-xs text-slate-400">
          <span class="h-px flex-1 bg-slate-200" />ou<span class="h-px flex-1 bg-slate-200" />
        </div>
        <VBtn variant="outlined" block :disabled="loading || checking" @click="oidc">
          Entrar com conta corporativa
        </VBtn>
      </template>

      <VAlert v-if="error" type="error" role="alert">{{ error }}</VAlert>
    </section>

    <AppModal :open="changeOpen" title="Defina sua nova senha" @close="closeChange">
      <form id="first-access-form" class="grid gap-3" :aria-busy="loading" @submit.prevent="submitNewPassword">
        <p class="text-sm">Este é o seu primeiro acesso (ou a senha padrão ainda está ativa). Escolha uma nova senha para continuar.</p>
        <div class="field">
          <VTextField v-model="newPassword" label="Nova senha" type="password" autocomplete="new-password" minlength="8" required />
        </div>
        <div class="field">
          <VTextField v-model="confirmPassword" label="Confirmar nova senha" type="password" autocomplete="new-password" minlength="8" required />
        </div>
        <small>Mínimo de 8 caracteres, com letras e números, diferente da senha padrão.</small>
        <VAlert v-if="changeError" type="error" role="alert">{{ changeError }}</VAlert>
      </form>
      <template #actions>
        <VBtn variant="outlined" :disabled="loading" @click="closeChange">Cancelar</VBtn>
        <VBtn type="submit" variant="flat" color="primary" form="first-access-form" :loading="loading" :disabled="loading">
          {{ loading ? "Salvando..." : "Salvar nova senha" }}
        </VBtn>
      </template>
    </AppModal>
  </div>
</template>

<style scoped>
.login-checking { display: flex; align-items: center; gap: 8px; margin: 0 0 8px; color: #748197; font-size: 12.5px; }
</style>
