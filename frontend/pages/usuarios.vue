<script setup lang="ts">
import { RefreshCw, ShieldAlert, UserPlus } from "lucide-vue-next";
import { onMounted, reactive, ref } from "vue";
import type { AdminUser, Role, UserSummary } from "~/types/api";
import Button from "~/components/ui/Button.vue";

definePageMeta({ middleware: "admin" });

const api = useApi();
const auth = useAuthStore();
const users = ref<AdminUser[]>([]);
const loading = ref(true);
const saving = ref(false);
const updating = ref(new Set<string>());
const error = ref("");
const formError = ref("");
const success = ref("");
const showCreate = ref(false);
const form = reactive<{ name: string; email: string; role: Role }>({
  name: "",
  email: "",
  role: "VIEWER",
});

const roleLabels: Record<Role, string> = {
  VIEWER: "Visualizador",
  ANALYST: "Analista",
  ADMIN: "Administrador",
};

function formatDate(value: string | null): string {
  if (!value) return "Nunca";
  return new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" }).format(
    new Date(value),
  );
}

async function load(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    users.value = (await api.get<{ items: AdminUser[] }>("/usuarios")).items;
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "Não foi possível carregar os usuários.";
  } finally {
    loading.value = false;
  }
}

function openCreate(): void {
  form.name = "";
  form.email = "";
  form.role = "VIEWER";
  formError.value = "";
  showCreate.value = true;
}

async function createUser(): Promise<void> {
  if (saving.value) return;
  saving.value = true;
  formError.value = "";
  success.value = "";
  try {
    const response = await api.post<{ user: UserSummary }>("/usuarios", {
      name: form.name.trim(),
      email: form.email.trim(),
      role: form.role,
    });
    showCreate.value = false;
    success.value = `${response.user.name} foi criado com a senha padrão e deverá alterá-la no primeiro acesso.`;
    await load();
  } catch (caught) {
    formError.value = caught instanceof Error ? caught.message : "Não foi possível criar o usuário.";
  } finally {
    saving.value = false;
  }
}

async function updateUser(user: AdminUser, changes: { role?: Role; active?: boolean }): Promise<void> {
  if (updating.value.has(user.id)) return;
  updating.value = new Set(updating.value).add(user.id);
  error.value = "";
  success.value = "";
  try {
    const response = await api.patch<{ user: UserSummary }>(`/usuarios/${user.id}`, changes);
    Object.assign(user, response.user);
    success.value = `${response.user.name} foi atualizado.`;
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "Não foi possível atualizar o usuário.";
    await load();
  } finally {
    const next = new Set(updating.value);
    next.delete(user.id);
    updating.value = next;
  }
}

function changeRole(user: AdminUser, event: Event): void {
  const role = (event.target as HTMLSelectElement).value as Role;
  if (role !== user.role) void updateUser(user, { role });
}

onMounted(load);
</script>

<template>
  <ModuleWorkspace
    eyebrow="Administração temporária"
    title="Usuários"
    description="Ferramenta provisória para os testes de autenticação local."
  >
    <div class="stack users-page">
      <section class="temporary-warning" role="note">
        <ShieldAlert :size="19" aria-hidden="true" />
        <div>
          <strong>Página temporária e não listada no menu</strong>
          <p>Somente administradores podem abrir esta URL. Remova a página quando os testes terminarem.</p>
        </div>
      </section>

      <div v-if="success" class="message success-message" role="status">{{ success }}</div>
      <div v-if="error" class="message error-message" role="alert">
        <span>{{ error }}</span>
        <Button class="text-button" type="button" variant="ghost" size="sm" @click="load">Tentar novamente</Button>
      </div>

      <section class="surface users-card">
        <header class="users-header">
          <div>
            <h2>Usuários cadastrados</h2>
            <p>{{ users.length }} usuário(s). O login local utiliza o e-mail completo.</p>
          </div>
          <div class="header-actions">
            <Button variant="outline" :disabled="loading" @click="load">
              <RefreshCw :size="15" /> Atualizar
            </Button>
            <Button variant="default" data-testid="new-user" @click="openCreate">
              <UserPlus :size="16" /> Novo usuário
            </Button>
          </div>
        </header>

        <div v-if="loading && !users.length" class="list-state" role="status">
          <span class="spinner" /> Carregando usuários...
        </div>
        <div v-else-if="!users.length && !error" class="empty-state">
          <h2>Nenhum usuário cadastrado</h2>
          <p>Crie o primeiro usuário para iniciar os testes.</p>
        </div>
        <div v-else class="table-wrap" :class="{ refreshing: loading }" :aria-busy="loading">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Usuário</TableHead>
                <TableHead>Perfil</TableHead>
                <TableHead>Autenticação</TableHead>
                <TableHead>Último acesso</TableHead>
                <TableHead>Situação</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow v-for="user in users" :key="user.id" :data-testid="`user-row-${user.id}`">
                <TableCell>
                  <strong class="user-name">{{ user.name }}</strong>
                  <span class="user-email">{{ user.email }}</span>
                  <small v-if="user.id === auth.user?.id" class="self-label">Sua conta</small>
                </TableCell>
                <TableCell>
                  <select
                    class="role-select"
                    :value="user.role"
                    :disabled="updating.has(user.id) || user.id === auth.user?.id"
                    :aria-label="`Perfil de ${user.name}`"
                    @change="changeRole(user, $event)"
                  >
                    <option v-for="(label, role) in roleLabels" :key="role" :value="role">{{ label }}</option>
                  </select>
                </TableCell>
                <TableCell><span class="provider">{{ user.authProvider }}</span></TableCell>
                <TableCell>{{ formatDate(user.lastLoginAt) }}</TableCell>
                <TableCell>
                  <span class="status" :class="user.active ? 'status--on' : 'status--off'">
                    {{ user.active ? "Ativo" : "Inativo" }}
                  </span>
                </TableCell>
                <TableCell class="action-cell">
                  <Button
                    class="text-button"
                    type="button"
                    :disabled="updating.has(user.id) || user.id === auth.user?.id"
                    variant="ghost"
                    size="sm"
                    @click="updateUser(user, { active: !user.active })"
                  >
                    {{ user.active ? "Desativar" : "Reativar" }}
                  </Button>
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </div>
      </section>
    </div>

    <AppModal :open="showCreate" title="Novo usuário" @close="showCreate = false">
      <form id="create-user-form" class="user-form" :aria-busy="saving" @submit.prevent="createUser">
        <p>O usuário receberá a senha padrão e deverá definir uma nova senha no primeiro acesso.</p>
        <label class="field">
          <span>Nome</span>
          <input v-model="form.name" required minlength="1" autocomplete="off" autofocus />
        </label>
        <label class="field">
          <span>E-mail</span>
          <input v-model="form.email" required type="email" autocomplete="off" />
        </label>
        <label class="field">
          <span>Perfil</span>
          <select v-model="form.role">
            <option v-for="(label, role) in roleLabels" :key="role" :value="role">{{ label }}</option>
          </select>
        </label>
        <p v-if="formError" class="form-error" role="alert">{{ formError }}</p>
      </form>
      <template #actions>
        <Button variant="outline" :disabled="saving" @click="showCreate = false">Cancelar</Button>
        <Button type="submit" variant="default" form="create-user-form" :loading="saving">
          {{ saving ? "Criando..." : "Criar usuário" }}
        </Button>
      </template>
    </AppModal>
  </ModuleWorkspace>
</template>

<style scoped>
.users-page { max-width: 1280px; margin: 0 auto; }
.temporary-warning { display: flex; gap: 12px; align-items: flex-start; border: 1px solid #e8c979; border-radius: 12px; padding: 13px 15px; background: #fff9e8; color: #735511; }
.temporary-warning strong { display: block; font-size: 13px; }
.temporary-warning p { margin: 3px 0 0; font-size: 12px; }
.message { display: flex; justify-content: space-between; gap: 12px; border-radius: 10px; padding: 11px 14px; font-size: 13px; }
.success-message { border: 1px solid #bdd9b3; background: #eff8eb; color: #376229; }
.error-message { border: 1px solid #edc1bc; background: #fff1ef; color: #934338; }
.users-card { overflow: hidden; }
.users-header { display: flex; align-items: center; justify-content: space-between; gap: 20px; padding: 18px 20px; border-bottom: 1px solid #e3e8ef; }
.users-header h2 { margin: 0; color: #213857; font-size: 17px; }
.users-header p { margin: 4px 0 0; color: #728096; font-size: 12px; }
.header-actions { display: flex; gap: 8px; }
.table-wrap { overflow-x: auto; transition: opacity 0.15s ease; }
.table-wrap.refreshing { opacity: 0.58; }
.list-state { display: flex; min-height: 220px; align-items: center; justify-content: center; gap: 10px; color: #718096; }
.user-name, .user-email, .self-label { display: block; }
.user-name { color: #233c5e; }
.user-email { margin-top: 2px; color: #68788f; font-size: 12px; }
.self-label { width: fit-content; margin-top: 5px; border-radius: 999px; padding: 2px 6px; background: #eaf1fa; color: #315a89; font-size: 10px; font-weight: 700; }
.role-select { min-width: 150px; border: 1px solid #d5deea; border-radius: 8px; padding: 7px 9px; background: #fff; color: #263d5d; }
.role-select:disabled { background: #f2f4f7; color: #7c8797; }
.provider { border-radius: 6px; padding: 3px 7px; background: #eef3f8; color: #455e7c; font-size: 11px; font-weight: 800; }
.status { border-radius: 999px; padding: 4px 9px; font-size: 11px; font-weight: 750; }
.status--on { background: #eaf5e5; color: #39702b; }
.status--off { background: #f4eeee; color: #8b4a44; }
.action-cell { text-align: right; }
.user-form { display: grid; gap: 14px; }
.user-form > p { margin: 0; color: #65758b; font-size: 13px; line-height: 1.5; }
.form-error { color: #a33f35 !important; }
@media (max-width: 760px) {
  .users-header { align-items: flex-start; flex-direction: column; }
  .header-actions { width: 100%; }
  .header-actions .el-button { flex: 1; }
}
</style>
