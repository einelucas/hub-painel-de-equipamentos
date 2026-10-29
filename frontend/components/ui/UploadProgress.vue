<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from "vue";
import { VProgressLinear } from "vuetify/components";

/**
 * Progresso de um envio de arquivo, com as duas fases do fluxo real:
 * - "uploading": bytes subindo (barra determinística quando o total é
 *   conhecido; indeterminada quando não — sem anunciar "0%").
 * - "processing": o servidor recebeu o arquivo e está trabalhando (sempre
 *   indeterminado, com cronômetro opcional).
 */
const props = withDefaults(
  defineProps<{
    /** `true` = enviando bytes; `false` = processando no servidor. */
    uploading: boolean;
    /** Percentual do envio (0–100); `null`/`undefined` = total desconhecido. */
    percent?: number | null;
    uploadLabel?: string;
    processingLabel?: string;
    /** Linha de contexto (ex.: nome do arquivo em envio). */
    detail?: string;
    /** Cronômetro durante o processamento (gerido aqui). */
    showElapsed?: boolean;
    warning?: string;
    /** Prefixo dos test-ids: raiz, `-status`, `-bar` e `-elapsed`. */
    testId?: string;
  }>(),
  {
    percent: null,
    uploadLabel: "Enviando arquivo",
    processingLabel: "Processando no servidor",
    detail: "",
    showElapsed: false,
    warning: "",
    testId: undefined,
  },
);

const elapsed = ref(0);
let timer: ReturnType<typeof setInterval> | null = null;

watch(() => [props.uploading, props.showElapsed] as const, ([uploading, showElapsed]) => {
  if (timer) clearInterval(timer);
  timer = null;
  elapsed.value = 0;
  if (!uploading && showElapsed) {
    timer = setInterval(() => { elapsed.value += 1; }, 1000);
  }
}, { immediate: true });
onUnmounted(() => {
  if (timer) clearInterval(timer);
  timer = null;
});

const knownPercent = computed(() => typeof props.percent === "number");
const statusText = computed(() => {
  if (props.uploading) {
    return knownPercent.value
      ? `${props.uploadLabel}… ${props.percent}%`
      : `${props.uploadLabel}…`;
  }
  return `${props.processingLabel}…`;
});

function childTestId(suffix: string): string | undefined {
  return props.testId ? `${props.testId}${suffix}` : undefined;
}
</script>

<template>
  <div class="upload-progress" :data-testid="props.testId">
    <p
      class="upload-progress__status"
      role="status"
      aria-live="polite"
      :data-testid="childTestId('-status')"
    >
      {{ statusText }}
      <span v-if="props.detail" class="upload-progress__detail">{{ props.detail }}</span>
      <span
        v-if="!props.uploading && props.showElapsed"
        class="upload-progress__elapsed"
        :data-testid="childTestId('-elapsed')"
      >{{ elapsed }}s</span>
    </p>

    <VProgressLinear
      class="upload-progress__bar"
      :model-value="props.uploading && knownPercent ? (props.percent ?? 0) : undefined"
      :indeterminate="!props.uploading || !knownPercent"
      color="primary"
      bg-color="primary"
      bg-opacity="0.12"
      :height="8"
      rounded
      :aria-label="props.uploading ? props.uploadLabel : props.processingLabel"
      :data-testid="childTestId('-bar')"
    />

    <p v-if="props.warning" class="upload-progress__warn">{{ props.warning }}</p>
  </div>
</template>

<style scoped>
.upload-progress {
  display: grid;
  gap: 8px;
  border: 1px solid var(--rule, #dde5ef);
  border-radius: 10px;
  padding: 12px 14px;
}

.upload-progress__status {
  margin: 0;
  font-size: 12.5px;
  font-weight: 700;
}

.upload-progress__detail {
  color: var(--muted, #6b7a8f);
  font-weight: 500;
  margin-left: 6px;
}

.upload-progress__elapsed {
  color: var(--muted, #6b7a8f);
  font-weight: 500;
  margin-left: 6px;
}

.upload-progress__warn {
  margin: 0;
  color: var(--muted, #6b7a8f);
  font-size: 11.5px;
}
</style>
