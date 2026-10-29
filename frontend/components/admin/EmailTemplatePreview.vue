<script setup lang="ts">
import { mdiCellphone, mdiMonitor } from "@mdi/js";
import { VBtn } from "vuetify/components";
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import type { EmailTemplatePreview } from "~/types/notifications";

defineProps<{ preview: EmailTemplatePreview | null; loading?: boolean }>();

const DESKTOP_WIDTH = 760;
const MOBILE_WIDTH = 390;
const VISIBLE_HEIGHT = 620;
const STAGE_HORIZONTAL_SPACE = 28;

const device = ref<"desktop" | "mobile">("desktop");
const stageEl = ref<HTMLElement | null>(null);
const stageWidth = ref(0);
const frameClass = computed(() => ({ mobile: device.value === "mobile" }));
const designWidth = computed(() => (device.value === "desktop" ? DESKTOP_WIDTH : MOBILE_WIDTH));
const scale = computed(() => {
  const available = stageWidth.value - STAGE_HORIZONTAL_SPACE;
  if (available <= 0) return 1;
  return Math.min(1, available / designWidth.value);
});
const frameStyle = computed(() => ({
  width: `${designWidth.value}px`,
  height: `${Math.round(VISIBLE_HEIGHT / scale.value)}px`,
  transform: `scale(${scale.value})`,
}));
const canvasStyle = computed(() => ({
  width: `${Math.round(designWidth.value * scale.value)}px`,
  height: `${VISIBLE_HEIGHT}px`,
}));

let observer: ResizeObserver | null = null;
function measure() {
  stageWidth.value = stageEl.value?.clientWidth ?? 0;
}

onMounted(() => {
  measure();
  if (typeof ResizeObserver !== "undefined" && stageEl.value) {
    observer = new ResizeObserver(measure);
    observer.observe(stageEl.value);
  }
});

onBeforeUnmount(() => {
  observer?.disconnect();
  observer = null;
});
</script>

<template>
  <section class="tpl-preview">
    <header class="tpl-preview-toolbar">
      <div class="tpl-preview-subject">
        <small>Assunto</small>
        <strong>{{ preview?.subject || "Pré-visualização pendente" }}</strong>
        <span v-if="preview?.sample" class="tpl-sample-pill">Dados fictícios</span>
      </div>
      <div class="tpl-device-toggle" role="group" aria-label="Visualização do e-mail">
        <VBtn
          type="button"
          :variant="device === 'desktop' ? 'tonal' : 'text'"
          size="small"
          :aria-pressed="device === 'desktop'"
          :prepend-icon="mdiMonitor"
          @click="device = 'desktop'"
        >
          Desktop
        </VBtn>
        <VBtn
          type="button"
          :variant="device === 'mobile' ? 'tonal' : 'text'"
          size="small"
          :aria-pressed="device === 'mobile'"
          :prepend-icon="mdiCellphone"
          @click="device = 'mobile'"
        >
          Celular
        </VBtn>
      </div>
    </header>

    <div ref="stageEl" class="tpl-preview-stage" :class="frameClass" :aria-busy="loading">
      <!-- sandbox vazio: sem scripts, sem mesma origem e sem formulários. -->
      <div v-if="preview" class="tpl-preview-canvas" :style="canvasStyle">
        <iframe
          class="tpl-preview-frame"
          title="Pré-visualização do e-mail"
          :srcdoc="preview.html"
          :style="frameStyle"
          sandbox=""
          referrerpolicy="no-referrer"
        />
      </div>
      <div v-else class="tpl-preview-empty">
        {{ loading ? "Renderizando pré-visualização..." : "Preencha o modelo para visualizar o e-mail." }}
      </div>
      <div v-if="loading && preview" class="tpl-preview-loading">Atualizando pré-visualização...</div>
    </div>

    <details v-if="preview" class="tpl-preview-text">
      <summary>Versão em texto simples (alternativa)</summary>
      <pre>{{ preview.text }}</pre>
    </details>
  </section>
</template>

<style scoped>
.tpl-preview { display: grid; gap: 10px; min-width: 0; }
.tpl-preview-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 10px; flex-wrap: wrap; }
.tpl-preview-subject { display: grid; gap: 2px; min-width: 0; }
.tpl-preview-subject small { font-size: 10px; text-transform: uppercase; letter-spacing: 0.06em; color: #7c8ba0; }
.tpl-preview-subject strong { font-size: 12px; color: #24364f; overflow-wrap: anywhere; }
.tpl-sample-pill { justify-self: start; margin-top: 2px; background: #fff4df; color: #92620f; border-radius: 6px; padding: 2px 7px; font-size: 10px; font-weight: 700; }
.tpl-device-toggle { display: inline-flex; gap: 4px; }
.tpl-preview-stage { position: relative; display: flex; justify-content: center; align-items: flex-start; background: #eef2f8; border: 1px solid #dde5ef; border-radius: 12px; padding: 14px; min-height: 648px; overflow: hidden; }
.tpl-preview-canvas { position: relative; flex: 0 0 auto; }
.tpl-preview-frame { position: absolute; top: 0; left: 0; transform-origin: top left; border: 0; background: #fff; border-radius: 10px; box-shadow: 0 10px 30px rgba(30, 47, 71, 0.12); }
.tpl-preview-empty { align-self: center; color: #64748b; font-size: 12px; }
.tpl-preview-loading { position: absolute; top: 10px; right: 14px; background: rgba(36, 54, 79, 0.9); color: #fff; border-radius: 6px; padding: 4px 8px; font-size: 10px; }
.tpl-preview-text summary { cursor: pointer; font-size: 11px; color: #304f7e; }
.tpl-preview-text pre { margin: 8px 0 0; padding: 10px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; font-size: 11px; line-height: 1.5; white-space: pre-wrap; max-height: 180px; overflow: auto; }
</style>
