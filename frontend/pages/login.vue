<script setup lang="ts">
import Button from "~/components/ui/Button.vue";

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
        <label class="field">
          <span>E-mail</span>
          <input v-model="email" type="email" autocomplete="username" required autofocus />
        </label>
        <label class="field">
          <span>Senha</span>
          <input v-model="password" type="password" autocomplete="current-password" required />
        </label>
        <Button type="submit" variant="default" class="login-submit mt-1" :disabled="checking" :loading="loading">
          {{ loading ? "Entrando..." : "Entrar" }}
        </Button>
      </form>

      <template v-if="oidcConfigured">
        <div class="my-4 flex items-center gap-3 text-xs text-slate-400">
          <span class="h-px flex-1 bg-slate-200" />ou<span class="h-px flex-1 bg-slate-200" />
        </div>
        <Button variant="outline" class="login-submit" :disabled="loading || checking" @click="oidc">
          Entrar com conta corporativa
        </Button>
      </template>

      <p v-if="error" class="login-error" role="alert">{{ error }}</p>
    </section>

    <AppModal :open="changeOpen" title="Defina sua nova senha" @close="closeChange">
      <form id="first-access-form" class="grid gap-3" :aria-busy="loading" @submit.prevent="submitNewPassword">
        <p class="text-sm">Este é o seu primeiro acesso (ou a senha padrão ainda está ativa). Escolha uma nova senha para continuar.</p>
        <label class="field">
          <span>Nova senha</span>
          <input v-model="newPassword" type="password" autocomplete="new-password" minlength="8" required />
        </label>
        <label class="field">
          <span>Confirmar nova senha</span>
          <input v-model="confirmPassword" type="password" autocomplete="new-password" minlength="8" required />
        </label>
        <small>Mínimo de 8 caracteres, com letras e números, diferente da senha padrão.</small>
        <p v-if="changeError" class="login-error" role="alert">{{ changeError }}</p>
      </form>
      <template #actions>
        <Button variant="outline" :disabled="loading" @click="closeChange">Cancelar</Button>
        <Button type="submit" variant="default" form="first-access-form" :loading="loading">
          {{ loading ? "Salvando..." : "Salvar nova senha" }}
        </Button>
      </template>
    </AppModal>
  </div>
</template>

<style scoped>
.login-checking { display: flex; align-items: center; gap: 8px; margin: 0 0 8px; color: #748197; font-size: 12.5px; }
</style>
