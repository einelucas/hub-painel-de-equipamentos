<script setup lang="ts">
import Button from "~/components/ui/Button.vue";
import { VAutocomplete } from "vuetify/components/VAutocomplete";
import { computed, ref, watch } from "vue";
import { FlaskConical, Search, Send } from "lucide-vue-next";
import type {
  MailProviderId,
  NotificationEquipmentOption,
} from "~/types/notifications";

type SettingsPanel = {
  mode: "log" | "sandbox" | "live";
  testInbox: string | null;
  providers: { id: MailProviderId; name: string; configured: boolean }[];
};

const props = defineProps<{
  settings: SettingsPanel | null;
  busy?: boolean;
  equipmentOptions: NotificationEquipmentOption[];
  equipmentId: string | null;
  useSample: boolean;
}>();

const emit = defineEmits<{
  "update:equipmentId": [value: string | null];
  "update:useSample": [value: boolean];
  send: [provider: MailProviderId];
}>();

const provider = ref<MailProviderId>("resend");
const search = ref("");

const sandbox = computed(() => props.settings?.mode === "sandbox");
const selectedProvider = computed(() =>
  props.settings?.providers.find((item) => item.id === provider.value),
);
const filtered = computed(() => {
  const term = search.value.trim().toLowerCase();
  const options = props.equipmentOptions;
  return (term ? options.filter((item) => item.name.toLowerCase().includes(term)) : options).slice(0, 80);
});
const providerOptions = computed(() =>
  (props.settings?.providers ?? []).map((item) => ({
    title: `${item.name}${item.configured ? "" : " (não configurado)"}`,
    value: item.id,
  })),
);
const equipmentSelectOptions = computed(() => [
  { title: "Selecione um equipamento", value: "" },
  ...filtered.value.map((item) => ({
    title: `${item.name}${item.unit?.name ? " · " + item.unit.name : ""}`,
    value: item.id,
  })),
]);
const disabled = computed(
  () =>
    !props.settings?.testInbox ||
    props.busy ||
    (props.settings?.mode !== "log" && !selectedProvider.value?.configured),
);

watch(
  () => props.settings,
  (value) => {
    if (!value) return;
    provider.value = value.providers.find((item) => item.id === "resend" && item.configured)?.id
      ?? (value.providers[0]?.id ?? "resend");
  },
  { immediate: true },
);
</script>

<template>
  <section class="tpl-test">
    <header class="tpl-test-head">
      <strong><FlaskConical :size="14" /> Enviar e-mail de teste</strong>
      <span class="tpl-test-inbox">{{ settings?.testInbox || "NOTIFICATION_TEST_INBOX não configurado" }}</span>
    </header>

    <p class="tpl-test-hint">
      O destino é sempre a caixa de testes — nenhum destinatário operacional é acionado.
      <template v-if="sandbox">
        <strong>Modo sandbox:</strong> o envio usa automaticamente dados fictícios. A
        seleção de equipamento abaixo vale apenas para a pré-visualização local.
      </template>
    </p>

    <div class="tpl-test-grid">
      <div class="field">
        <VAutocomplete
          v-model="provider"
          :items="providerOptions"
          item-title="title"
          item-value="value"
          variant="outlined"
          color="primary"
          density="comfortable"
          hide-details="auto"
          label="Provedor para este teste"
        />
      </div>
    </div>

    <label class="tpl-check">
      <input
        type="checkbox"
        :checked="useSample"
        :disabled="busy"
        @change="emit('update:useSample', ($event.target as HTMLInputElement).checked)"
      />
      <span>
        Usar dados fictícios
        <small v-if="sandbox">No sandbox o envio é sempre fictício.</small>
      </span>
    </label>

    <template v-if="!useSample">
      <label class="field">
        <span><Search :size="12" /> Buscar equipamento (dados reais)</span>
        <input v-model="search" placeholder="Nome do equipamento" />
      </label>
      <div class="field">
        <VAutocomplete
          data-testid="email-test-equipment"
          :model-value="equipmentId ?? ''"
          :items="equipmentSelectOptions"
          item-title="title"
          item-value="value"
          variant="outlined"
          color="primary"
          density="comfortable"
          hide-details="auto"
          label="Equipamento para pré-visualização e teste"
          @update:model-value="emit('update:equipmentId', String($event || '') || null)"
        />
      </div>
    </template>

    <Button

      type="button"

      :disabled="disabled"

      variant="default"

      size="sm"

      @click="emit('send', provider)"

    >
      <Send :size="14" /> {{ busy ? "Enviando..." : "Enviar e-mail de teste" }}
    </Button>
  </section>
</template>

<style scoped>
.tpl-test { display: grid; gap: 9px; border: 1px solid #e2e8f0; border-radius: 12px; padding: 14px; background: #f8fafc; }
.tpl-test-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; flex-wrap: wrap; }
.tpl-test-head strong { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; color: #24364f; }
.tpl-test-inbox { background: #eef3fb; color: #304f7e; border-radius: 6px; padding: 3px 8px; font-size: 10px; font-weight: 700; overflow-wrap: anywhere; }
.tpl-test-hint { margin: 0; font-size: 11px; line-height: 1.5; color: #64748b; }
.tpl-test-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.tpl-check { display: flex; gap: 8px; align-items: start; font-size: 12px; color: #24364f; }
.tpl-check input { margin-top: 2px; accent-color: #304f7e; }
.tpl-check span { display: grid; gap: 1px; }
.tpl-check small { color: #92620f; font-size: 10px; }
.tpl-test .el-button { justify-self: start; }
@media (max-width: 700px) { .tpl-test-grid { grid-template-columns: minmax(0, 1fr); } }
</style>
