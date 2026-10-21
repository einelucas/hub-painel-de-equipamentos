<script setup lang="ts">
import { ref } from "vue";
import { Code2, RotateCcw, Save, Sparkles } from "lucide-vue-next";
import EmailTemplateSettings from "~/components/admin/EmailTemplateSettings.vue";
import EmailTemplateVariables from "~/components/admin/EmailTemplateVariables.vue";
import type { EmailTemplateDraft } from "~/types/notifications";

type TextField = "subject" | "title" | "intro" | "body" | "buttonLabel" | "footer" | "customHtml";

const props = defineProps<{ modelValue: EmailTemplateDraft; busy?: boolean }>();
const emit = defineEmits<{
  "update:modelValue": [value: EmailTemplateDraft];
  save: [];
  reset: [];
}>();

const mode = ref<"visual" | "html">("visual");
const activeField = ref<TextField>("body");

function setField<K extends keyof EmailTemplateDraft>(
  key: K,
  value: EmailTemplateDraft[K],
): void {
  emit("update:modelValue", { ...props.modelValue, [key]: value });
}

function insertToken(token: string): void {
  if (activeField.value === "customHtml") {
    setField("customHtml", (props.modelValue.customHtml ?? "") + token);
    return;
  }
  const field = activeField.value;
  setField(field, props.modelValue[field] + token);
}

function selectMode(next: "visual" | "html"): void {
  mode.value = next;
  if (next === "html" && props.modelValue.useCustomHtml) {
    activeField.value = "customHtml";
  }
}

function toggleAdvanced(): void {
  const next = !props.modelValue.useCustomHtml;
  emit("update:modelValue", {
    ...props.modelValue,
    useCustomHtml: next,
    customHtml: props.modelValue.customHtml ?? "",
  });
  mode.value = next ? "html" : "visual";
  activeField.value = next ? "customHtml" : "body";
}
</script>

<template>
  <section class="tpl-editor stack">
    <div class="tpl-editor-tabs" role="tablist" aria-label="Modo de edição do modelo">
      <button
        type="button"
        role="tab"
        :aria-selected="mode === 'visual'"
        :class="{ active: mode === 'visual' }"
        @click="selectMode('visual')"
      >
        <Sparkles :size="13" /> Editor visual
      </button>
      <button
        type="button"
        role="tab"
        :aria-selected="mode === 'html'"
        :class="{ active: mode === 'html' }"
        @click="selectMode('html')"
      >
        <Code2 :size="13" /> HTML avançado
      </button>
    </div>

    <template v-if="mode === 'visual'">
      <div class="tpl-editor-grid">
        <label class="field">
          <span>Título principal</span>
          <input
            :value="modelValue.title"
            maxlength="160"
            @focus="activeField = 'title'"
            @input="setField('title', ($event.target as HTMLInputElement).value)"
          />
        </label>
        <label class="field">
          <span>Assunto do e-mail</span>
          <input
            :value="modelValue.subject"
            maxlength="200"
            @focus="activeField = 'subject'"
            @input="setField('subject', ($event.target as HTMLInputElement).value)"
          />
        </label>
        <label class="field tpl-span-2">
          <span>Texto introdutório</span>
          <textarea
            :value="modelValue.intro"
            rows="2"
            maxlength="1000"
            @focus="activeField = 'intro'"
            @input="setField('intro', ($event.target as HTMLTextAreaElement).value)"
          />
        </label>
        <label class="field tpl-span-2">
          <span>Corpo da mensagem</span>
          <textarea
            :value="modelValue.body"
            rows="5"
            maxlength="6000"
            @focus="activeField = 'body'"
            @input="setField('body', ($event.target as HTMLTextAreaElement).value)"
          />
        </label>
        <label class="field">
          <span>Texto do botão de ação</span>
          <input
            :value="modelValue.buttonLabel"
            maxlength="80"
            @focus="activeField = 'buttonLabel'"
            @input="setField('buttonLabel', ($event.target as HTMLInputElement).value)"
          />
        </label>
        <label class="field tpl-span-2">
          <span>Rodapé</span>
          <textarea
            :value="modelValue.footer"
            rows="2"
            maxlength="1000"
            @focus="activeField = 'footer'"
            @input="setField('footer', ($event.target as HTMLTextAreaElement).value)"
          />
        </label>
      </div>

      <div class="tpl-editor-columns">
        <EmailTemplateVariables @insert="insertToken" />
        <EmailTemplateSettings
          :model-value="modelValue"
          :disabled="busy"
          @update:model-value="emit('update:modelValue', { ...modelValue, ...$event })"
        />
      </div>
    </template>

    <template v-else>
      <div class="tpl-html-warning">
        <Code2 :size="15" />
        <span>
          O HTML completo substitui o layout padrão. Scripts, formulários, URLs
          <code>javascript:</code> e atributos de evento são removidos pelo backend
          antes de salvar e de enviar. Use <code>{equipamento}</code>, <code>{tag}</code> e
          demais variáveis entre chaves.
        </span>
      </div>
      <template v-if="modelValue.useCustomHtml">
        <label class="field">
          <span>HTML do modelo</span>
          <textarea
            class="tpl-html-editor"
            :value="modelValue.customHtml ?? ''"
            rows="22"
            maxlength="120000"
            spellcheck="false"
            @focus="activeField = 'customHtml'"
            @input="setField('customHtml', ($event.target as HTMLTextAreaElement).value)"
          />
        </label>
        <EmailTemplateVariables @insert="insertToken" />
      </template>
      <button v-else type="button" class="btn small tpl-html-enable" @click="toggleAdvanced">
        <Code2 :size="14" /> Ativar HTML avançado
      </button>
    </template>

    <div class="tpl-editor-actions">
      <button type="button" class="btn primary small" :disabled="busy" @click="emit('save')">
        <Save :size="14" /> {{ busy ? "Salvando..." : "Salvar alterações" }}
      </button>
      <button type="button" class="btn small" :disabled="busy" @click="emit('reset')">
        <RotateCcw :size="14" /> Restaurar padrão
      </button>
      <button
        type="button"
        class="tpl-advanced-toggle"
        :class="{ active: modelValue.useCustomHtml }"
        :aria-pressed="modelValue.useCustomHtml"
        @click="toggleAdvanced"
      >
        <Code2 :size="13" />
        {{ modelValue.useCustomHtml ? "Modo avançado ativo" : "Usar HTML avançado" }}
      </button>
    </div>
  </section>
</template>

<style scoped>
.tpl-editor { gap: 14px; }
.tpl-editor-tabs { display: flex; gap: 4px; border-bottom: 1px solid #dfe6f0; }
.tpl-editor-tabs button { display: inline-flex; align-items: center; gap: 5px; padding: 8px 10px; font-size: 12px; color: #64748b; border-bottom: 2px solid transparent; }
.tpl-editor-tabs button.active { color: #304f7e; font-weight: 800; border-color: #304f7e; }
.tpl-editor-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.tpl-span-2 { grid-column: 1 / -1; }
.tpl-editor-columns { display: grid; grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr); gap: 12px; align-items: start; }
.tpl-editor-actions { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.tpl-advanced-toggle { display: inline-flex; align-items: center; gap: 5px; margin-left: auto; border: 1px solid #d7e0ec; border-radius: 7px; padding: 7px 10px; font-size: 11px; color: #64748b; background: #fff; }
.tpl-advanced-toggle.active { border-color: #304f7e; color: #304f7e; background: #eef3fb; font-weight: 700; }
.tpl-html-warning { display: flex; gap: 8px; align-items: start; background: #fff8ec; border: 1px solid #f2ddb4; border-radius: 8px; padding: 10px; font-size: 11px; line-height: 1.5; color: #8a5a10; }
.tpl-html-warning code { background: #fff; border: 1px solid #eadcc1; border-radius: 4px; padding: 0 3px; }
.tpl-html-enable { justify-self: start; }
.tpl-html-editor { font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: 12px; line-height: 1.5; min-height: 320px; }
@media (max-width: 1100px) {
  .tpl-editor-grid, .tpl-editor-columns { grid-template-columns: minmax(0, 1fr); }
  .tpl-advanced-toggle { margin-left: 0; }
}
</style>
