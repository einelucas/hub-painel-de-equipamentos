<script setup lang="ts">
import { computed, ref } from "vue";
import { Save } from "lucide-vue-next";
import type { UserSummary } from "~/types/api";
import type { Unit, UserUnits } from "~/types/equipment";

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
  current.value = null;
  feedback.value = "";
  if (!selectedUser.value) return;
  loadingUser.value = true;
  error.value = "";
  try {
    current.value = await api.get<UserUnits>(`/usuarios/${selectedUser.value}/units`);
    checked.value = new Set(current.value.units.map((unit) => unit.id));
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "Não foi possível carregar os acessos.";
  } finally {
    loadingUser.value = false;
  }
}

function toggle(unitId: string): void {
  const next = new Set(checked.value);
  if (next.has(unitId)) next.delete(unitId);
  else next.add(unitId);
  checked.value = next;
}

async function save(): Promise<void> {
  if (!selectedUser.value || isAdminUser.value) return;
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
    <p class="access-intro">
      O perfil define o que o usuário pode fazer; o vínculo abaixo define em quais unidades.
    </p>

    <p v-if="loading" class="access-hint"><span class="spinner spinner-small" /> Carregando usuários...</p>
    <p v-else-if="error" class="access-error" role="alert">{{ error }}</p>
    <template v-else>
      <label class="field">
        <span>Usuário</span>
        <select v-model="selectedUser" data-testid="access-user" @change="selectUser">
          <option value="">Selecione um usuário</option>
          <option v-for="user in users" :key="user.id" :value="user.id">
            {{ user.name }} · {{ user.role }}
          </option>
        </select>
      </label>

      <p v-if="loadingUser" class="access-hint"><span class="spinner spinner-small" /> Carregando acessos...</p>
      <template v-else-if="current">
        <p v-if="isAdminUser" class="access-admin" data-testid="access-admin-notice">
          Este usuário é ADMIN e enxerga todas as unidades por perfil. Acesso individual não se aplica.
        </p>
        <template v-else>
          <ul class="access-list">
            <li v-for="unit in units" :key="unit.id">
              <label>
                <input
                  type="checkbox"
                  :checked="checked.has(unit.id)"
                  :data-testid="`access-unit-${unit.id}`"
                  @change="toggle(unit.id)"
                >
                <span>{{ unit.code }} · {{ unit.name }}</span>
              </label>
            </li>
          </ul>
          <p v-if="units.length === 0" class="access-hint">Nenhuma unidade cadastrada ainda.</p>
          <div class="access-actions">
            <span v-if="feedback" class="access-feedback">{{ feedback }}</span>
            <button type="button" class="btn small primary" :disabled="saving" data-testid="access-save" @click="save">
              <Save :size="13" /> {{ saving ? "Salvando..." : "Salvar acessos" }}
            </button>
          </div>
        </template>
      </template>
    </template>
  </section>
</template>

<style scoped>
.access { display: grid; gap: 12px; padding: 4px 0 10px; }
.access-intro { margin: 0; color: #65748a; font-size: 12px; }
.access-hint { display: flex; align-items: center; gap: 8px; margin: 0; color: #8b96a5; font-size: 12px; }
.access-error { margin: 0; color: #a4453a; font-size: 12px; font-weight: 700; }
.access-admin { margin: 0; border-radius: 9px; background: #e8f1fc; padding: 9px 11px; color: #27456f; font-size: 12px; font-weight: 700; }
.access-list { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); margin: 0; padding: 0; gap: 7px; list-style: none; }
.access-list label { display: flex; align-items: center; gap: 8px; color: #2b3e58; font-size: 12.5px; }
.access-list input { width: 15px; height: 15px; }
.access-actions { display: flex; align-items: center; justify-content: flex-end; gap: 12px; }
.access-feedback { color: #477a32; font-size: 12px; font-weight: 700; }
.spinner-small { width: 14px; height: 14px; border-width: 2px; }
@media (max-width: 620px) { .access-list { grid-template-columns: 1fr; } }
</style>
