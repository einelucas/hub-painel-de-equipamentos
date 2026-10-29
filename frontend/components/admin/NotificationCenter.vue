<script setup lang="ts">
import { mdiEmailCheckOutline, mdiRefresh, mdiSendOutline } from "@mdi/js";
import { VAutocomplete } from "vuetify/components/VAutocomplete";
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { AlertTriangle, CheckCircle2, CircleHelp, Clock3, Settings2 } from "lucide-vue-next";
import EmailTemplateEditor from "~/components/admin/EmailTemplateEditor.vue";
import EmailTemplatePreview from "~/components/admin/EmailTemplatePreview.vue";
import EmailTestPanel from "~/components/admin/EmailTestPanel.vue";
import { VBtn } from "vuetify/components";
import type {
  EmailTemplate,
  EmailTemplateDraft,
  EmailTemplatePreview as EmailTemplatePreviewData,
  EmailTemplateTestResult,
  MailProviderId,
  NotificationEquipmentOption,
  NotificationKind,
} from "~/types/notifications";

type Kind = NotificationKind;
type Tab = "settings" | "rules" | "recipients" | "templates" | "history";
type ProviderId = MailProviderId;
type ProviderStatus = { id: ProviderId; name: string; configured: boolean; sender: string | null };
type Settings = {
  mode: "log" | "sandbox" | "live";
  provider: string;
  activeProvider: ProviderId;
  providers: ProviderStatus[];
  configured: boolean;
  sender: string | null;
  testInbox: string | null;
};
type Rule = { kind: Kind; enabled: boolean; includeResponsible: boolean; daysBefore: number; recipientEmails: string[]; subjectTemplate: string; bodyTemplate: string };
type Delivery = { id: string; kind: string; equipmentId: string | null; status: string; mode: string; provider: ProviderId; recipientSummary: string; subject: string; failureReason: string | null; attempts: number; createdAt: string; processedAt: string | null };

const api = useApi();
const tab = ref<Tab>("settings");
const selectedKind = ref<Kind>("KICKOFF");
const settings = ref<Settings | null>(null);
const testProvider = ref<ProviderId>("resend");
const testProviderStatus = computed(() => settings.value?.providers.find((item) => item.id === testProvider.value));
const rules = ref<Rule[]>([]);
const deliveries = ref<Delivery[]>([]);
const loading = ref(true);
const busy = ref(false);
const error = ref("");
const notice = ref("");
const mailSubject = ref("Teste de notificações — Painel de Equipamentos");
const mailBody = ref("Esta é uma mensagem de teste do Hub. Nenhuma notificação operacional foi disparada.");
const recipientsText = ref("");
const templates = ref<EmailTemplate[]>([]);
const templateDraft = ref<EmailTemplateDraft | null>(null);
const templatePreview = ref<EmailTemplatePreviewData | null>(null);
const previewLoading = ref(false);
const previewError = ref("");
const equipmentOptions = ref<NotificationEquipmentOption[]>([]);
const selectedEquipmentId = ref<string | null>(null);
const useSampleData = ref(true);
let previewTimer: ReturnType<typeof setTimeout> | undefined;
let previewVersion = 0;
const selected = computed(() => rules.value.find((item) => item.kind === selectedKind.value));
const names: Record<Kind, string> = {
  KICKOFF: "Kickoff (conclusão da fase 5)",
  FUP: "FUP (conclusão da fase 7)",
  STARTUP_REMINDER: "Lembrete de startup (data programada)",
  NEGOTIATION_OVERDUE: "Negociação atrasada",
  DELIVERY_REMINDER: "Entrega próxima (prazo calculado)",
  COMPLETED: "Equipamento concluído (fase 8)",
};
const tabs: { key: Tab; name: string }[] = [
  { key: "settings", name: "Configuração" },
  { key: "rules", name: "Regras" },
  { key: "recipients", name: "Destinatários" },
  { key: "templates", name: "Modelos" },
  { key: "history", name: "Histórico" },
];
const stateLabels: Record<string, string> = {
  PENDING: "Aguardando",
  PROCESSING: "Processando",
  ACCEPTED: "Aceito pelo provedor",
  SIMULATED: "Simulado (sem envio)",
  SKIPPED: "Ignorado",
  FAILED: "Falha",
};

function chooseRule(kind: Kind): void {
  selectedKind.value = kind;
  recipientsText.value = selected.value?.recipientEmails.join("\n") ?? "";
  applyTemplate(kind);
}

function applyTemplate(kind: Kind): void {
  const template = templates.value.find((item) => item.kind === kind);
  if (!template) return;
  templateDraft.value = {
    subject: template.subject,
    title: template.title,
    intro: template.intro,
    body: template.body,
    buttonLabel: template.buttonLabel,
    footer: template.footer,
    customHtml: template.customHtml,
    useCustomHtml: template.useCustomHtml,
    showDetails: template.showDetails,
    showAlert: template.showAlert,
    showButton: template.showButton,
    showFooter: template.showFooter,
  };
  schedulePreview();
}

async function load(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    const [configuration, list, history, templateList, equipments] = await Promise.all([
      api.get<Settings>("/notifications/settings"),
      api.get<{ items: Rule[] }>("/notifications/rules"),
      api.get<{ items: Delivery[] }>("/notifications/deliveries", { limit: "100" }),
      api.get<{ items: EmailTemplate[] }>("/notifications/templates"),
      api.get<{ items: NotificationEquipmentOption[] }>("/equipments", {
        pageSize: "100", sortBy: "name", sortDir: "asc",
      }),
    ]);
    settings.value = configuration;
    // Prioriza Resend para testes com Gmail quando as credenciais estão disponíveis.
    testProvider.value = configuration.providers.find((p) => p.id === "resend" && p.configured)?.id
      ?? configuration.activeProvider;
    rules.value = list.items;
    deliveries.value = history.items;
    templates.value = templateList.items;
    equipmentOptions.value = equipments.items;
    chooseRule(selectedKind.value);
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "Não foi possível carregar as notificações.";
  } finally {
    loading.value = false;
  }
}

async function save(): Promise<void> {
  const rule = selected.value;
  if (!rule || busy.value) return;
  busy.value = true;
  error.value = "";
  notice.value = "";
  try {
    const recipientEmails = recipientsText.value
      .split(/[\n;,]+/).map((email) => email.trim()).filter(Boolean);
    const updated = await api.put<Rule>("/notifications/rules/" + rule.kind, {
      ...rule,
      recipientEmails,
      daysBefore: ["STARTUP_REMINDER", "DELIVERY_REMINDER"].includes(rule.kind) ? rule.daysBefore : 0,
    });
    const index = rules.value.findIndex((value) => value.kind === rule.kind);
    if (index !== -1) rules.value[index] = updated;
    recipientsText.value = updated.recipientEmails.join("\n");
    notice.value = "Regra salva. Alterações auditadas pelo sistema.";
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "Falha ao salvar a regra.";
  } finally {
    busy.value = false;
  }
}

async function sendTest(): Promise<void> {
  if (busy.value || !settings.value?.testInbox) return;
  busy.value = true;
  error.value = "";
  notice.value = "";
  try {
    const item = await api.post<Delivery>("/notifications/test", {
      provider: testProvider.value, subject: mailSubject.value, body: mailBody.value,
    });
    notice.value = item.status === "ACCEPTED"
      ? "O provedor aceitou o envio. Verifique a caixa de testes para confirmar a entrega."
      : item.status === "SIMULATED"
        ? "Teste simulado: nenhuma mensagem foi enviada."
        : "Teste registrado com estado " + (stateLabels[item.status] ?? item.status) + ".";
    if (item.failureReason) error.value = item.failureReason;
    deliveries.value.unshift(item);
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "Não foi possível iniciar o teste.";
  } finally {
    busy.value = false;
  }
}

function schedulePreview(): void {
  clearTimeout(previewTimer);
  previewTimer = setTimeout(() => void loadPreview(), 350);
}

async function loadPreview(): Promise<void> {
  const draft = templateDraft.value;
  if (!draft) return;
  const version = ++previewVersion;
  previewLoading.value = true;
  try {
    const result = await api.post<EmailTemplatePreviewData>(
      "/notifications/templates/" + selectedKind.value + "/preview",
      {
        ...draft,
        equipmentId: useSampleData.value ? null : selectedEquipmentId.value,
        useSample: useSampleData.value,
      },
    );
    if (version !== previewVersion) return;
    templatePreview.value = result;
    previewError.value = "";
  } catch (caught) {
    if (version !== previewVersion) return;
    previewError.value = caught instanceof Error ? caught.message : "Falha ao renderizar a pré-visualização.";
  } finally {
    if (version === previewVersion) previewLoading.value = false;
  }
}

async function saveTemplate(): Promise<void> {
  const draft = templateDraft.value;
  if (!draft || busy.value) return;
  busy.value = true;
  error.value = "";
  notice.value = "";
  try {
    const updated = await api.put<EmailTemplate>(
      "/notifications/templates/" + selectedKind.value,
      draft,
    );
    templates.value = templates.value.map((item) => (item.kind === updated.kind ? updated : item));
    applyTemplate(updated.kind);
    notice.value = "Modelo salvo. O HTML sanitizado é exatamente o que será enviado.";
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "Falha ao salvar o modelo.";
  } finally {
    busy.value = false;
  }
}

async function resetTemplate(): Promise<void> {
  if (busy.value || !confirm("Restaurar este modelo para o padrão do Hub? As alterações atuais serão perdidas.")) return;
  busy.value = true;
  error.value = "";
  notice.value = "";
  try {
    const updated = await api.post<EmailTemplate>(
      "/notifications/templates/" + selectedKind.value + "/reset",
    );
    templates.value = templates.value.map((item) => (item.kind === updated.kind ? updated : item));
    applyTemplate(updated.kind);
    notice.value = "Modelo restaurado para o padrão.";
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "Falha ao restaurar o modelo.";
  } finally {
    busy.value = false;
  }
}

async function sendTemplateTest(provider: MailProviderId): Promise<void> {
  const draft = templateDraft.value;
  if (!draft || busy.value) return;
  busy.value = true;
  error.value = "";
  notice.value = "";
  try {
    const result = await api.post<EmailTemplateTestResult>(
      "/notifications/templates/" + selectedKind.value + "/test",
      {
        ...draft,
        provider,
        equipmentId: useSampleData.value ? null : selectedEquipmentId.value,
        useSample: useSampleData.value,
      },
    );
    templatePreview.value = result.preview;
    const status = result.delivery.status;
    notice.value = status === "ACCEPTED"
      ? "O provedor aceitou o envio. Confira a caixa de testes" + (result.preview.sample ? " (dados fictícios)." : ".")
      : status === "SIMULATED"
        ? "Teste simulado: nenhuma mensagem foi enviada."
        : "Teste registrado com estado " + (stateLabels[status] ?? status) + ".";
    if (result.delivery.failureReason) error.value = result.delivery.failureReason;
    try {
      deliveries.value = (await api.get<{ items: Delivery[] }>("/notifications/deliveries", { limit: "100" })).items;
    } catch {
      // O teste já foi registrado; falhar ao recarregar o histórico não deve
      // induzir um reenvio.
    }
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "Não foi possível enviar o teste.";
  } finally {
    busy.value = false;
  }
}

async function process(): Promise<void> {
  if (busy.value || !confirm("Processar agora notificações reais e lembretes pendentes conforme o modo do ambiente?")) return;
  busy.value = true;
  error.value = "";
  notice.value = "";
  try {
    const result = await api.post<{ scheduled: number; processed: number }>("/notifications/process");
    notice.value = "Agendadas: " + result.scheduled + " · Processadas: " + result.processed + ".";
    deliveries.value = (await api.get<{ items: Delivery[] }>("/notifications/deliveries")).items;
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "Falha no processamento.";
  } finally {
    busy.value = false;
  }
}

async function retry(item: Delivery): Promise<void> {
  if (busy.value || !confirm("Confirme no Outlook que a mensagem não foi enviada. Repetir pode gerar duplicidade. Continuar?")) return;
  busy.value = true;
  error.value = "";
  try {
    await api.post("/notifications/deliveries/" + item.id + "/retry");
    await load();
    notice.value = "Mensagem recolocada na fila para processamento.";
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "Falha ao solicitar reenvio.";
  } finally {
    busy.value = false;
  }
}

function formatDate(value: string | null): string {
  if (!value) return "—";
  return new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" }).format(new Date(value));
}

watch(templateDraft, () => schedulePreview(), { deep: true });
watch([selectedEquipmentId, useSampleData], () => schedulePreview());
onBeforeUnmount(() => clearTimeout(previewTimer));
onMounted(load);
</script>

<template>
  <section class="notification-center stack">
    <header class="notify-heading">
      <div>
        <h3>Central de notificações</h3>
        <p>Microsoft Graph, caixa de testes, destinatários e acompanhamento dos envios.</p>
      </div>
      <VBtn size="small" variant="outlined" :disabled="busy || loading" :prepend-icon="mdiRefresh" @click="load">
         Atualizar
      </VBtn>
    </header>

    <div v-if="error" class="notify-message notify-error" role="alert"><AlertTriangle :size="16" /> {{ error }}</div>
    <div v-if="notice" class="notify-message notify-success" role="status"><CheckCircle2 :size="16" /> {{ notice }}</div>
    <div v-if="loading" role="status" class="notify-empty" aria-busy="true">Carregando configuração de e-mails...</div>

    <template v-else>
      <div class="notify-tabs" role="tablist" aria-label="Central de notificações">
        <VBtn
          v-for="item in tabs"
          :key="item.key"
          :variant="tab === item.key ? 'tonal' : 'text'"
          type="button"
          role="tab"
          size="small"
          :aria-selected="tab === item.key" :class="{ active: tab === item.key }" @click="tab = item.key">
          {{ item.name }}
        </VBtn>
      </div>

      <div v-if="tab === 'settings'" class="notify-panel stack">
        <div class="notify-heading"><h4><Settings2 :size="16" /> Configuração do provedor</h4></div>
        <div class="notify-status">
          <strong>{{ settings?.provider }}</strong>
          <span :class="{ good: settings?.configured }">{{ settings?.configured ? "Configurado" : "Configuração pendente" }}</span>
        </div>
        <dl class="notify-details">
          <div><dt>Provedor operacional</dt><dd>{{ settings?.provider }} ({{ settings?.configured ? "configurado" : "pendente" }})</dd></div>
          <div><dt>Modo atual</dt><dd>{{ settings?.mode === "sandbox" ? "Caixa de testes (sandbox)" : settings?.mode === "live" ? "Produção — destinatários reais" : "Simulação local — sem envio" }}</dd></div>
          <div><dt>Remetente</dt><dd>{{ settings?.sender || "Não configurado" }}</dd></div>
          <div><dt>Caixa de testes</dt><dd>{{ settings?.testInbox || "NOTIFICATION_TEST_INBOX não definido" }}</dd></div>
        </dl>
        <p class="notify-hint"><CircleHelp :size="15" /> Credenciais, provedor operacional e modo são definidos exclusivamente no ambiente do backend. O seletor abaixo altera somente o envio de teste, nunca o provedor das notificações operacionais.</p>
        <div class="notify-providers">
          <div v-for="provider in settings?.providers" :key="provider.id" class="notify-provider">
            <strong>{{ provider.name }}</strong>
            <span :class="{ good: provider.configured }">{{ provider.configured ? "Disponível" : "Pendente" }}</span>
            <small>{{ provider.sender || "Remetente não configurado" }}</small>
          </div>
        </div>
        <div class="notify-test-box stack">
          <strong>Enviar teste para caixa autorizada</strong>
          <div class="field">
            <VAutocomplete
              v-model="testProvider"
              :items="(settings?.providers ?? []).map((p) => ({ title: `${p.name}${p.configured ? '' : ' (não configurado)'}`, value: p.id }))"
              item-title="title"
              item-value="value"
              label="Provedor para este teste"
            />
          </div>
          <p>O destino é fixo: {{ settings?.testInbox || "caixa ainda não configurada" }}. No modo sandbox todos os envios, inclusive alertas operacionais, são redirecionados para ela.</p>
          <label class="field"><span>Assunto</span><input v-model="mailSubject" maxlength="200" /></label>
          <label class="field"><span>Mensagem</span><textarea v-model="mailBody" rows="4" maxlength="4000" /></label>
          <VBtn size="small" variant="tonal" :disabled="busy || !settings?.testInbox || (settings?.mode !== 'log' && !testProviderStatus?.configured)" :prepend-icon="mdiSendOutline" @click="sendTest"> {{ busy ? "Enviando..." : "Enviar teste" }}</VBtn>
        </div>
      </div>

      <div v-else-if="tab === 'rules' || tab === 'recipients'" class="notify-panel stack">
        <div class="field">
          <VAutocomplete
            :model-value="selectedKind"
            :items="Object.entries(names).map(([kind, label]) => ({ title: label, value: kind }))"
            item-title="title"
            item-value="value"
            label="Evento"
            @update:model-value="chooseRule($event as Kind)"
          />
        </div>
        <template v-if="selected">
          <template v-if="tab === 'rules'">
            <label class="notify-check"><input v-model="selected.enabled" type="checkbox" /> Regra ativa</label>
            <label class="notify-check"><input v-model="selected.includeResponsible" type="checkbox" /> Incluir automaticamente o responsável cadastrado no equipamento</label>
            <label v-if="(selected.kind === 'STARTUP_REMINDER' || selected.kind === 'DELIVERY_REMINDER')" class="field"><span>Dias antes do startup (0 a 365)</span><input v-model.number="selected.daysBefore" type="number" min="0" max="365" /></label>
            <p class="notify-hint">Kickoff: conclusão da fase 5. FUP e conclusão: fase 7→8. Lembretes de startup, negociação vencida e entrega próxima são gerados pelo worker usando as fórmulas já existentes no Hub. Todas as regras começam desativadas.</p>
          </template>
          <template v-else>
            <label class="notify-check"><input v-model="selected.includeResponsible" type="checkbox" /> Incluir responsável do equipamento</label>
            <label class="field"><span>Destinatários fixos — um endereço por linha</span><textarea v-model="recipientsText" rows="6" placeholder="equipe@empresa.com" /></label>
            <p class="notify-hint">No modo sandbox os endereços são registrados, mas não recebem e-mails: apenas a caixa de testes recebe. Em produção, os destinatários são deduplicados.</p>
          </template>
          <VBtn size="small" variant="tonal" :disabled="busy" :prepend-icon="mdiEmailCheckOutline" @click="save"> {{ busy ? "Salvando..." : "Salvar configuração" }}</VBtn>
        </template>
      </div>

      <div v-else-if="tab === 'templates'" class="notify-panel stack tpl-workspace">
        <div class="tpl-workspace-head">
          <div class="field">
            <VAutocomplete
              :model-value="selectedKind"
              :items="Object.entries(names).map(([kind, label]) => ({ title: label, value: kind }))"
              item-title="title"
              item-value="value"
              label="Tipo de notificação"
              @update:model-value="chooseRule($event as Kind)"
            />
          </div>
          <p class="notify-hint"><CircleHelp :size="15" /> O modelo salvo vale para todos os envios deste tipo. A pré-visualização e o teste usam exatamente o HTML que será enviado; o teste nunca atinge destinatários operacionais.</p>
        </div>

        <div v-if="previewError" class="notify-message notify-error" role="alert"><AlertTriangle :size="16" /> {{ previewError }}</div>

        <div class="tpl-workspace-grid">
          <div class="tpl-workspace-editor">
            <EmailTemplateEditor
              v-if="templateDraft"
              v-model="templateDraft"
              :busy="busy"
              @save="saveTemplate"
              @reset="resetTemplate"
            />
            <div v-else class="notify-empty">Modelo indisponível para este tipo.</div>
          </div>
          <div class="tpl-workspace-preview">
            <EmailTemplatePreview :preview="templatePreview" :loading="previewLoading" />
            <EmailTestPanel
              :settings="settings"
              :busy="busy"
              :equipment-options="equipmentOptions"
              :equipment-id="selectedEquipmentId"
              :use-sample="useSampleData"
              @update:equipment-id="selectedEquipmentId = $event"
              @update:use-sample="useSampleData = $event"
              @send="sendTemplateTest"
            />
          </div>
        </div>
      </div>

      <div v-else class="notify-panel stack">
        <div class="notify-heading">
          <h4><Clock3 :size="16" /> Histórico de tentativas</h4>
          <VBtn size="small" variant="outlined" :disabled="busy" @click="process">Processar fila agora</VBtn>
        </div>
        <p class="notify-hint">Aceito pelo Graph significa HTTP 202 (aceito para processamento), não confirmação de entrega na caixa postal. Falhas são registradas para reenvio manual.</p>
        <div v-if="!deliveries.length" class="notify-empty">Nenhuma tentativa de envio registrada.</div>
        <div v-for="item in deliveries" :key="item.id" class="notify-delivery">
          <div class="notify-heading">
            <strong>{{ item.subject }}</strong>
            <span class="notify-pill" :class="{ good: item.status === 'ACCEPTED', bad: item.status === 'FAILED' }">{{ stateLabels[item.status] ?? item.status }}</span>
          </div>
          <p>{{ item.recipientSummary || "Sem destinatários" }} · {{ formatDate(item.createdAt) }} · {{ item.mode }} · {{ item.provider === "graph" ? "Graph" : "Resend" }}</p>
          <p v-if="item.failureReason" class="notify-error-text">{{ item.failureReason }}</p>
          <VBtn v-if="item.status === 'FAILED' && item.attempts < 3" size="small" variant="outlined" :disabled="busy" @click="retry(item)">Reenviar após conferência</VBtn>
        </div>
      </div>
    </template>
  </section>
</template>

<style scoped>
.notification-center { width: 100%; min-width: 0; max-width: 100%; color: #24364f; }
.notify-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.notify-heading h3 { font-size: 17px; font-weight: 800; margin: 0; }
.notify-heading h4 { display: flex; align-items: center; gap: 7px; font-size: 14px; font-weight: 750; margin: 0; }
.notify-heading p, .notify-delivery p { margin: 4px 0; font-size: 12px; color: #64748b; }
.notify-tabs { display: flex; flex-wrap: wrap; gap: 4px; border-bottom: 1px solid #dfe6f0; }
.notify-panel { padding: 12px 0; }
.notify-panel :deep(.field) { max-width: 100%; }
.notify-panel textarea { resize: vertical; min-height: 90px; width: 100%; }
.notify-panel .btn { align-self: flex-start; }
.notify-status { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
.notify-status strong { font-size: 14px; }
.notify-providers { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; }
.notify-provider { padding: 12px; border: 1px solid #e2e8f0; border-radius: 9px; display: grid; gap: 6px; }
.notify-provider strong { font-size: 12px; }
.notify-provider span { font-size: 11px; color: #a16207; }
.notify-provider span.good { color: #307241; }
.notify-provider small { color: #64748b; overflow-wrap: anywhere; }
.notify-status span, .notify-pill { border-radius: 7px; padding: 4px 9px; background: #fff4df; color: #92620f; font-size: 11px; }
.notify-status .good, .notify-pill.good { background: #e8f5e8; color: #2b6c3b; }
.notify-pill.bad { background: #fff0ed; color: #b02f20; }
.notify-details { display: grid; gap: 0; border: 1px solid #e6ebf3; border-radius: 10px; overflow: hidden; }
.notify-details div { display: grid; grid-template-columns: 140px 1fr; padding: 11px 12px; gap: 12px; border-bottom: 1px solid #edf1f7; font-size: 12px; }
.notify-details div:last-child { border-bottom: none; }
.notify-details dt { color: #64748b; }
.notify-details dd { overflow-wrap: anywhere; font-weight: 650; margin: 0; }
.notify-hint { display: flex; gap: 8px; align-items: start; color: #64748b; font-size: 12px; line-height: 1.5; margin: 0; }
.notify-test-box { background: #f8fafc; border: 1px solid #e2e8f0; padding: 16px; border-radius: 12px; }
.notify-test-box p { font-size: 12px; color: #64748b; margin: 0; }
.notify-check { display: flex; gap: 8px; align-items: center; font-size: 13px; }
.notify-check input { accent-color: #304f7e; }
.notify-delivery { border: 1px solid #e2e8f0; border-radius: 10px; padding: 12px; display: grid; gap: 4px; }
.notify-delivery strong { font-size: 12px; font-weight: 700; max-width: 75%; overflow-wrap: anywhere; }
.notify-empty { padding: 28px 12px; color: #64748b; text-align: center; font-size: 12px; }
.notify-message { display: flex; gap: 8px; align-items: center; border-radius: 8px; padding: 10px; font-size: 12px; }
.notify-error { background: #fff1f0; color: #a32c24; }
.notify-success { background: #eff8ed; color: #306c2e; }
.notify-error-text { color: #b02f20 !important; }
.tpl-workspace { gap: 14px; }
.tpl-workspace-head { display: grid; gap: 6px; }
.tpl-workspace-grid { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 18px; align-items: start; }
.tpl-workspace-editor, .tpl-workspace-preview { display: grid; gap: 14px; min-width: 0; }
@media (max-width: 1250px) {
  .tpl-workspace-grid { grid-template-columns: minmax(0, 1fr); }
}
</style>
