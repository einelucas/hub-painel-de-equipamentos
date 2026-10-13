<script setup lang="ts">
import { computed, ref } from "vue";
import { Save } from "lucide-vue-next";
import type { UserSummary } from "~/types/api";
import type { Unit, UserUnits } from "~/types/equipment";
import SearchableSelect from "~/components/ui/SearchableSelect.vue";

/** Reaproveita os endpoints da Etapa 4; não recria cadastro de usuários. */
const emit = defineEmits<{ changed: [] }>();

const api = useApi();
const users = ref<UserSummary[]>([]);
const units = ref<Unit[]>([]);
const selectedUser = ref("");
const current = ref<UserUnits | null>(null);
const checked = ref<Set<string>>(new Set());
const loading = ref(true);
const loadingUser = ref(false);
const saving = ref(false);
const error = ref("");
const feedback = ref("");
let userVersion = 0;

const userOptions = computed(() =>
  users.value.map((user) => ({ id: user.id, label: `${user.name} · ${user.role}`, searchText: user.email })),
);
const isAdminUser = computed(() => current.value?.allUnits === true);

async function load(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    const [userResult, unitResult] = await Promise.all([
      api.get<{ items: UserSummary[] }>("/usuarios", { pageSize: 100 }),
      api.get<{ items: Unit[] }>("/units"),
    ]);
    users.value = userResult.items.filter((user) => user.active);
    units.value = unitResult.items;
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "Não foi possível carregar os usuários.";
  } finally {
    loading.value = false;
  }
}

async function selectUser(): Promise<void> {
  const version = ++userVersion;
  current.value = null;
  feedback.value = "";
  if (!selectedUser.value) {
    loadingUser.value = false;
    return;
  }
  loadingUser.value = true;
  error.value = "";
  try {
    const result = await api.get<UserUnits>(`/usuarios/${selectedUser.value}/units`);
    if (version !== userVersion) return;
    current.value = result;
    checked.value = new Set(result.units.map((unit) => unit.id));
  } catch (caught) {
    if (version !== userVersion) return;
    error.value = caught instanceof Error ? caught.message : "Não foi possível carregar os acessos.";
  } finally {
    if (version === userVersion) loadingUser.value = false;
  }
}

function toggle(unitId: string): void {
  const next = new Set(checked.value);
  if (next.has(unitId)) next.delete(unitId);
  else next.add(unitId);
  checked.value = next;
}

async function save(): Promise<void> {
  if (saving.value || loadingUser.value || !selectedUser.value || isAdminUser.value) return;
  saving.value = true;
  error.value = "";
  feedback.value = "";
  try {
    current.value = await api.put<UserUnits>(`/usuarios/${selectedUser.value}/units`, {
      unitIds: [...checked.value],
    });
    checked.value = new Set(current.value.units.map((unit) => unit.id));
    feedback.value = "Acessos atualizados.";
    emit("changed");
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "Não foi possível salvar os acessos.";
  } finally {
    saving.value = false;
  }
}

onMounted(load);
</script>

<template>
  <section class="access" data-testid="unit-access-admin">
    <header class="access-head">
      <h3>Acesso às unidades</h3>
      <p>O perfil define o que o usuário pode fazer; o vínculo abaixo define em quais unidades.</p>
    </header>

    <p v-if="loading" class="access-hint"><span class="spinner spinner-small" /> Carregando usuários...</p>
    <p v-else-if="error" class="access-error" role="alert">{{ error }}</p>
    <template v-else>
      <div class="field access-user">
        <span>Usuário</span>
        <SearchableSelect
          v-model="selectedUser"
          :options="userOptions"
          :clearable="false"
          label="Usuário"
          placeholder="Buscar por nome ou e-mail"
          empty-label="Selecione um usuário"
          test-id="access-user"
          @change="selectUser"
        />
      </div>

      <p v-if="loadingUser" class="access-hint"><span class="spinner spinner-small" /> Carregando acessos...</p>
      <template v-else-if="current">
        <p v-if="isAdminUser" class="access-admin" data-testid="access-admin-notice">
          Este usuário é ADMIN e enxerga todas as unidades por perfil. Acesso individual não se aplica.
        </p>
        <template v-else>
          <p v-if="units.length" class="access-count">{{ checked.size }} de {{ units.length }} unidades liberadas</p>
          <ul class="access-list">
            <li v-for="unit in units" :key="unit.id">
              <label :class="{ checked: checked.has(unit.id) }">
                <input
                  type="checkbox"
                  :checked="checked.has(unit.id)"
                  :data-testid="`access-unit-${unit.id}`"
                  @change="toggle(unit.id)"
                >
                <span>{{ unit.name }}</span>
              </label>
            </li>
          </ul>
          <p v-if="units.length === 0" class="access-hint">Nenhuma unidade cadastrada ainda.</p>
          <div class="access-actions">
            <span v-if="feedback" class="access-feedback">{{ feedback }}</span>
            <button type="button" class="btn small primary" :disabled="saving" data-testid="access-save" :aria-busy="saving" @click="save">
              <span v-if="saving" class="spinner-small" aria-hidden="true" /><Save v-else :size="13" /> {{ saving ? "Salvando..." : "Salvar acessos" }}
            </button>
          </div>
        </template>
      </template>
    </template>
  </section>
</template>

<style scoped>
.access { display: grid; gap: 14px; }
.access-head { padding-bottom: 12px; border-bottom: 1px solid var(--rule, #dde5ef); }
.access-head h3 { margin: 0; color: var(--ink, #1f3352); font-size: 17px; font-weight: 800; letter-spacing: -0.01em; }
.access-head p { margin: 2px 0 0; color: var(--muted, #6b7a8f); font-size: 12px; }
.access-user { max-width: 420px; }
.access-hint { display: flex; align-items: center; gap: 8px; margin: 0; color: var(--muted, #6b7a8f); font-size: 12px; }
.access-error { margin: 0; color: var(--stop, #a4453a); font-size: 12px; font-weight: 700; }
.access-admin { margin: 0; border-left: 3px solid var(--steel, #304f7e); border-radius: 8px; background: #e8f1fc; padding: 10px 12px; color: #27456f; font-size: 12px; font-weight: 700; }
.access-count { margin: 0; color: var(--muted, #6b7a8f); font-family: var(--mono, monospace); font-size: 11px; }
.access-list { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); margin: 0; padding: 0; gap: 8px; list-style: none; }
.access-list label {
  display: flex;
  align-items: center;
  gap: 10px;
  border: 1px solid var(--rule, #dde5ef);
  border-radius: 10px;
  padding: 10px 12px;
  background: #fff;
  color: var(--ink, #1f3352);
  font-size: 12.5px;
  font-weight: 700;
  cursor: pointer;
  transition: border-color 0.15s ease, background-color 0.15s ease;
}
.access-list label:hover { border-color: #c4d2e4; }
.access-list label.checked { border-color: var(--steel, #304f7e); background: #f1f6fd; }
.access-list label:focus-within { outline: 2px solid var(--steel, #304f7e); outline-offset: 2px; }
.access-list input { width: 16px; height: 16px; accent-color: var(--steel, #304f7e); }
.access-actions { display: flex; align-items: center; justify-content: flex-end; gap: 12px; border-top: 1px solid var(--rule, #dde5ef); padding-top: 12px; }
.access-feedback { color: var(--go, #3f7a2e); font-size: 12px; font-weight: 700; }
@media (prefers-reduced-motion: reduce) { .access-list label { transition: none; } }
</style>
